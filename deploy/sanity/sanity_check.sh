#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://localhost:8080}"
USER_ID="${USER_ID:-00000000-0000-0000-0000-000000000001}"
LOGFILE="${LOGFILE:-/tmp/collectors-merge.out}"
TIMEOUT="${TIMEOUT:-40}"

ok()   { echo -e "✅ $*"; }
fail() { echo -e "❌ $*"; exit 1; }

# repo root + env
cd "$(dirname "$0")/../.." || true
[ -f .env ] || fail ".env missing in repo root"
set -a; . ./.env; set +a
[ -n "${DATABASE_URL:-}" ] || fail "DATABASE_URL not set in .env"
ok "env loaded"

# DB connectivity
command -v psql >/dev/null || fail "psql not installed"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "select 1;" >/dev/null
ok "DB reachable"

# extension
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "create extension if not exists pg_trgm;" >/dev/null

# schema checks (robust)
present() {
  psql "$DATABASE_URL" -t -A -c "select case when to_regclass('$1') is not null then 't' else 'f' end" | tr -d '[:space:]'
}
P_ITEMS=$(present 'public.items')
P_HITS=$(present 'public.market_hits')
P_PREDS=$(present 'public.price_predictions')

if [[ "$P_ITEMS" != "t" || "$P_HITS" != "t" || "$P_PREDS" != "t" ]]; then
  fail "schema incomplete (items:$P_ITEMS market_hits:$P_HITS price_predictions:$P_PREDS)"
fi
ok "schema present (items, market_hits, price_predictions)"

# restart API
echo "🔄 restarting API…"
pkill -f "uvicorn .*services.collectors_merge.api.main:app" >/dev/null 2>&1 || true
pkill -f "uvicorn" >/dev/null 2>&1 || true
nohup ./deploy/run_uvicorn.sh >"$LOGFILE" 2>&1 &

# wait for /health
for i in $(seq 1 "$TIMEOUT"); do
  if curl -fsS "$BASE/health" >/dev/null 2>&1; then break; fi
  sleep 0.25
  [[ $i -eq $TIMEOUT ]] && { fail "API not reachable at $BASE (check $LOGFILE)"; }
done
ok "API /health reachable"

# /sanity/ready
READY=$(curl -sS "$BASE/sanity/ready" || true)
echo "$READY" | jq . >/dev/null 2>&1 || { echo "$READY"; fail "/sanity/ready returned non-JSON"; }
[[ "$(echo "$READY" | jq -r '.ok')" == "true" ]] || { echo "$READY" | jq .; fail "/sanity/ready failed"; }
ok "/sanity/ready ok"

# /sanity/e2e dry-run
E2E=$(curl -sS -X POST "$BASE/sanity/e2e?user_id=$USER_ID&category=lego" || true)
echo "$E2E" | jq . >/dev/null 2>&1 || { echo "$E2E"; fail "/sanity/e2e returned non-JSON"; }
[[ "$(echo "$E2E" | jq -r '.ok')" == "true" ]] || { echo "$E2E" | jq .; fail "/sanity/e2e failed"; }
ok "/sanity/e2e ok (comps_found: $(echo "$E2E" | jq -r '.steps.comps_found // 0'))"

# stop API (optional)
pkill -f "uvicorn .*services.collectors_merge.api.main:app" >/dev/null 2>&1 || true
pkill -f "uvicorn" >/dev/null 2>&1 || true

ok "all sanity checks passed"
