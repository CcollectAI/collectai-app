#!/usr/bin/env bash
# ============================================================================
# CollectAI — Data Bake startup script
# ============================================================================
# Idempotent EC2 startup that brings the backend + workers up for the
# pre-launch data bake. Each step maps to a Round 46 gotcha:
#
#   G1  Migration drift            → alembic-current diff + opt-in apply
#   G2  Memory pressure             → free-RAM check before catalog import
#   G3  Catalog non-idempotency     → row-count guard, --force flag to truncate
#   G4  Missing credentials          → enumerate active sources, log + warn
#   G5  Spend ramp                   → confirm MONTHLY_BUDGET_EUR set, ping Telegram
#   G6  Stale model                  → force MODEL_RETRAIN_ENABLED=true
#   G7  DB pool exhaustion           → bump DB_POOL_MAX=30 unless overridden
#
# Usage:
#   ./scripts/bake_start.sh                       # safe default — won't apply migrations or reimport
#   ./scripts/bake_start.sh --apply-migrations    # actually run alembic upgrade head
#   ./scripts/bake_start.sh --force-reimport      # TRUNCATE category_items + re-run import_all
#   ./scripts/bake_start.sh --apply-migrations --force-reimport
#
# Environment expected (from .env, sourced below):
#   DB_DSN, SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET,
#   OPENAI_API_KEY, OPS_API_KEY, MONTHLY_BUDGET_EUR,
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# ============================================================================

set -euo pipefail

# ── Args ────────────────────────────────────────────────────────────────────
APPLY_MIGRATIONS=0
FORCE_REIMPORT=0
for arg in "$@"; do
  case "$arg" in
    --apply-migrations) APPLY_MIGRATIONS=1 ;;
    --force-reimport)   FORCE_REIMPORT=1 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_DIR="$REPO_ROOT/server"
LOG_FILE="$REPO_ROOT/bake.log"
PID_FILE="$REPO_ROOT/bake.pid"

cd "$REPO_ROOT"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "FATAL: $*"; exit 1; }
section() { log ""; log "── $* ──"; }

section "CollectAI bake startup ($(date -u +%Y-%m-%dT%H:%M:%SZ))"

# ── Env ─────────────────────────────────────────────────────────────────────
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
  set +a
  log "loaded $REPO_ROOT/.env"
else
  die ".env not found at $REPO_ROOT/.env"
fi

[ -n "${DB_DSN:-}" ]            || die "DB_DSN not set"
[ -n "${SUPABASE_URL:-}" ]      || die "SUPABASE_URL not set"
[ -n "${OPS_API_KEY:-}" ]       || die "OPS_API_KEY not set (generate one: openssl rand -hex 16)"

# ── G6: force model retrain on for the bake ────────────────────────────────
export MODEL_RETRAIN_ENABLED="${MODEL_RETRAIN_ENABLED:-true}"
export MONITOR_ENABLED="${MONITOR_ENABLED:-true}"
export DEAL_DISCOVERY_ENABLED="${DEAL_DISCOVERY_ENABLED:-true}"
export CATALOG_LEARNING_ENABLED="${CATALOG_LEARNING_ENABLED:-true}"
export TASK_WORKER_ENABLED="${TASK_WORKER_ENABLED:-true}"
export MATVIEW_REFRESH_ENABLED="${MATVIEW_REFRESH_ENABLED:-true}"
export AUTO_DELIST_ENABLED="${AUTO_DELIST_ENABLED:-false}"   # not needed pre-launch
export CALIBRATION_ENABLED="${CALIBRATION_ENABLED:-true}"
export EVENT_SCRAPER_ENABLED="${EVENT_SCRAPER_ENABLED:-false}"  # not needed pre-launch

# ── G7: DB pool sizing for the bake (5 schedulers + uvicorn workers + admin) ──
export DB_POOL_MIN="${DB_POOL_MIN:-5}"
export DB_POOL_MAX="${DB_POOL_MAX:-30}"

# ── G5: spend cap ───────────────────────────────────────────────────────────
export MONTHLY_BUDGET_EUR="${MONTHLY_BUDGET_EUR:-150}"
log "spend cap: €${MONTHLY_BUDGET_EUR}/month (telegram alerts at 75/90/100%)"

# ── Stop any previous bake process ──────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" || echo "")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "stopping previous bake process (pid $OLD_PID)"
    kill "$OLD_PID" || true
    sleep 2
    kill -9 "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi
# Also catch any rogue uvicorn that wasn't tracked
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1

# ── G2: memory check before catalog import ──────────────────────────────────
section "G2: memory check"
if command -v free >/dev/null 2>&1; then
  TOTAL_MB=$(free -m | awk '/^Mem:/ {print $2}')
  AVAIL_MB=$(free -m | awk '/^Mem:/ {print $7}')
  log "RAM total=${TOTAL_MB}MB available=${AVAIL_MB}MB"
  if [ "$TOTAL_MB" -lt 3500 ]; then
    log "WARN: less than 4GB total RAM. Catalog import may OOM. Recommend t3.medium or larger."
    log "WARN: continuing in 5s — Ctrl-C to abort"
    sleep 5
  fi
else
  log "free(1) not available — skipping RAM check (probably macOS)"
fi

# ── G1: migration drift check ───────────────────────────────────────────────
section "G1: migration drift check"
cd "$SERVER_DIR"
if command -v alembic >/dev/null 2>&1; then
  CURRENT_REV=$(alembic current 2>/dev/null | tail -1 || echo "unknown")
  log "alembic current: ${CURRENT_REV}"
  PENDING=$(alembic history --indicate-current 2>/dev/null | grep -c '^Rev:' || echo "0")
  log "alembic history entries: ${PENDING}"
  # Show pending migrations
  if [ "$APPLY_MIGRATIONS" = "1" ]; then
    log "applying migrations (--apply-migrations was passed)"
    # G1 safety: refuse if any pending file contains destructive DROP without IF EXISTS
    DESTRUCTIVE=$(grep -lE 'DROP +(TABLE|COLUMN|SCHEMA|DATABASE)(?! +IF +EXISTS)' \
      "$REPO_ROOT/supabase/migrations/"*.sql 2>/dev/null | head -5 || true)
    if [ -n "$DESTRUCTIVE" ]; then
      log "WARN: destructive DROPs found in: $DESTRUCTIVE"
      log "WARN: aborting migration apply. Eyeball the file(s) and re-run."
      exit 2
    fi
    alembic upgrade head 2>&1 | tee -a "$LOG_FILE"
  else
    log "NOT applying migrations (pass --apply-migrations to actually run alembic upgrade head)"
    log "review unapplied migrations first: ls $REPO_ROOT/supabase/migrations/ | tail -10"
  fi
else
  log "WARN: alembic not in PATH — skipping migration check. Apply migrations manually via supabase SQL editor."
fi
cd "$REPO_ROOT"

# ── G8: schema drift check (verify code-vs-DB column alignment before bake) ──
section "G8: schema drift check"
if python3 "$REPO_ROOT/scripts/schema_drift_check.py" 2>&1 | tee -a "$LOG_FILE"; then
  log "schema drift check PASSED"
else
  log "❌ schema drift check FAILED — code expects columns the DB doesn't have"
  log "   run: python3 scripts/schema_drift_check.py --fix-suggest"
  log "   eyeball the suggestions, apply via psql, then re-run bake_start.sh"
  die "schema drift detected — bake aborted to prevent silent write failures"
fi

# ── G3a: catalog dedup pre-flight (verify pipelines are clean before import) ──
section "G3a: catalog dedup audit"
if python3 "$REPO_ROOT/scripts/catalog_dedup_check.py" 2>&1 | tee -a "$LOG_FILE"; then
  log "dedup audit PASSED"
else
  AUDIT_EXIT=$?
  if [ "$AUDIT_EXIT" = "2" ]; then
    die "dedup audit found BROKEN pipelines (exit 2). Fix imports before baking."
  fi
  log "WARN: dedup audit found internal duplicates. Round 14 dedup should suppress at DB level via merge-duplicates upsert, but review the report above."
  log "WARN: continuing in 5s — Ctrl-C to abort"
  sleep 5
fi

# ── G3: catalog idempotency guard ───────────────────────────────────────────
section "G3: catalog import"
# Use psql via DB_DSN to count rows. Falls back to Python if psql is missing.
CATALOG_COUNT=0
if command -v psql >/dev/null 2>&1; then
  CATALOG_COUNT=$(psql "$DB_DSN" -tAc "SELECT count(*) FROM public.category_items;" 2>/dev/null || echo "0")
  CATALOG_COUNT=${CATALOG_COUNT:-0}
else
  CATALOG_COUNT=$(python3 -c "
import asyncio, asyncpg, os
async def main():
    try:
        c = await asyncpg.connect(os.environ['DB_DSN'])
        n = await c.fetchval('SELECT count(*) FROM public.category_items')
        await c.close()
        print(n or 0)
    except Exception:
        print(0)
asyncio.run(main())
" 2>/dev/null || echo "0")
fi
log "category_items current row count: $CATALOG_COUNT"

if [ "$FORCE_REIMPORT" = "1" ]; then
  log "--force-reimport: TRUNCATE category_items then re-run import_all"
  if command -v psql >/dev/null 2>&1; then
    psql "$DB_DSN" -c "TRUNCATE TABLE public.category_items CASCADE;" || die "truncate failed"
  else
    python3 -c "
import asyncio, asyncpg, os
async def main():
    c = await asyncpg.connect(os.environ['DB_DSN'])
    await c.execute('TRUNCATE TABLE public.category_items CASCADE')
    await c.close()
asyncio.run(main())
" || die "truncate failed"
  fi
  CATALOG_COUNT=0
fi

if [ "$CATALOG_COUNT" -lt 1000 ]; then
  log "running pipelines/import_all (this takes 5-15 min, ~46k items)"
  cd "$SERVER_DIR"
  python3 -m pipelines.import_all 2>&1 | tee -a "$LOG_FILE" || die "import_all failed"
  cd "$REPO_ROOT"
else
  log "catalog already loaded ($CATALOG_COUNT items) — skipping import. Use --force-reimport to override."
fi

# ── G4: enumerate active data sources ──────────────────────────────────────
section "G4: data source inventory"
ACTIVE=()
for var in OPENAI_API_KEY FIRECRAWL_API_KEY SCRAPEDO_API_KEY SERPAPI_API_KEY \
           EBAY_APP_ID EBAY_CLIENT_ID TCGPLAYER_PUBLIC_KEY TCGPLAYER_BEARER_TOKEN \
           DISCOGS_PERSONAL_TOKEN ETSY_API_KEY REBRICKABLE_API_KEY POKEMONTCG_API_KEY \
           CARDMARKET_APP_TOKEN STOCKX_API_KEY PRICECHARTING_API_KEY \
           BRICKLINK_CONSUMER_KEY FAL_KEY; do
  if [ -n "${!var:-}" ]; then ACTIVE+=("$var"); fi
done
log "configured paid/keyed sources (${#ACTIVE[@]}): ${ACTIVE[*]}"
log "free unrestricted sources: eBay-html, Crawl4AI, Mercari-US, Vinted, Mavin.io, Google-Shopping (always-on)"

# ── Start uvicorn with all worker flags ────────────────────────────────────
section "starting uvicorn + workers"
cd "$SERVER_DIR"

if ! command -v uvicorn >/dev/null 2>&1; then
  if [ -x "$REPO_ROOT/.venv/bin/uvicorn" ]; then
    UVICORN="$REPO_ROOT/.venv/bin/uvicorn"
  else
    die "uvicorn not in PATH and no .venv/bin/uvicorn found"
  fi
else
  UVICORN=$(command -v uvicorn)
fi

nohup "$UVICORN" main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-2}" \
  >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
log "uvicorn started (pid $NEW_PID)"

# Wait for /healthz
sleep 4
HEALTH_URL="http://localhost:${PORT:-8000}/healthz"
for i in 1 2 3 4 5; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    log "healthz OK on attempt $i"
    break
  fi
  if [ "$i" = "5" ]; then
    log "WARN: healthz did not respond after 5 attempts. Tail bake.log for errors."
  else
    sleep 2
  fi
done

# ── G5: ping Telegram that the bake started ────────────────────────────────
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  MSG="🔥 CollectAI bake started%0A• ${#ACTIVE[@]} paid sources active%0A• ${CATALOG_COUNT} catalog items%0A• budget €${MONTHLY_BUDGET_EUR}/mo%0A• pid ${NEW_PID}"
  curl -fsS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${MSG}" -d "parse_mode=Markdown" \
    >/dev/null 2>&1 && log "telegram start ping sent" || log "telegram ping failed (non-fatal)"
fi

section "bake startup complete"
log "monitor: ./scripts/bake_status.sh   |   tail: ./scripts/bake_tail.sh   |   stop: ./scripts/bake_stop.sh"
