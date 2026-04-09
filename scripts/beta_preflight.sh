#!/usr/bin/env bash
# ============================================================
# Atlantis — Beta Pre-Flight Check
# ============================================================
# Run this before deploying to verify all required services
# are configured and reachable.
#
# Usage:
#   ./scripts/beta_preflight.sh              (uses .env)
#   ./scripts/beta_preflight.sh .env.beta    (uses custom env file)
# ============================================================

set -euo pipefail

ENV_FILE="${1:-.env}"
PASS=0
FAIL=0
WARN=0

green()  { printf "\033[32m✓ %s\033[0m\n" "$1"; PASS=$((PASS+1)); }
red()    { printf "\033[31m✗ %s\033[0m\n" "$1"; FAIL=$((FAIL+1)); }
yellow() { printf "\033[33m⚠ %s\033[0m\n" "$1"; WARN=$((WARN+1)); }

echo ""
echo "═══════════════════════════════════════════════"
echo "  Atlantis Beta Pre-Flight Check"
echo "═══════════════════════════════════════════════"
echo ""

# --- Load env file ---
if [ -f "$ENV_FILE" ]; then
  green "Env file found: $ENV_FILE"
  set -a; source "$ENV_FILE"; set +a
else
  red "Env file not found: $ENV_FILE"
  echo "  Create one from .env.beta: cp .env.beta .env"
  exit 1
fi

echo ""
echo "── 1. Frontend Configuration ──"

# Supabase mode
if [ "${EXPO_PUBLIC_SUPABASE_MODE:-}" = "real" ]; then
  green "SUPABASE_MODE = real"
elif [ "${EXPO_PUBLIC_SUPABASE_MODE:-}" = "strict" ]; then
  green "SUPABASE_MODE = strict"
else
  red "SUPABASE_MODE = ${EXPO_PUBLIC_SUPABASE_MODE:-unset} (must be 'real' or 'strict')"
fi

# Supabase URL
if [ -n "${EXPO_PUBLIC_SUPABASE_URL:-}" ]; then
  green "SUPABASE_URL configured"
else
  red "EXPO_PUBLIC_SUPABASE_URL missing"
fi

# API URL
if [ -n "${EXPO_PUBLIC_API_BASE_URL:-}" ]; then
  green "API_BASE_URL = $EXPO_PUBLIC_API_BASE_URL"
else
  red "EXPO_PUBLIC_API_BASE_URL missing"
fi

echo ""
echo "── 2. Backend Configuration ──"

# DB
if [ "${DB_ENABLED:-}" = "true" ]; then
  green "DB_ENABLED = true"
else
  red "DB_ENABLED = ${DB_ENABLED:-unset} (must be 'true')"
fi

# DEV_MODE
if [ "${DEV_MODE:-}" = "false" ]; then
  green "DEV_MODE = false"
else
  yellow "DEV_MODE = ${DEV_MODE:-unset} (should be 'false' for beta)"
fi

# Required backend keys
for var in SUPABASE_JWT_SECRET SUPABASE_URL OPS_API_KEY OPENAI_API_KEY; do
  val=$(eval echo "\${${var}:-}")
  if [ -n "$val" ] && [ "$val" != "sk-..." ] && [[ "$val" != *"placeholder"* ]]; then
    green "$var configured"
  else
    red "$var missing or placeholder"
  fi
done

# S3
for var in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
  val=$(eval echo "\${${var}:-}")
  if [ -n "$val" ] && [[ "$val" != "AKIA..." ]]; then
    green "$var configured"
  else
    red "$var missing or placeholder"
  fi
done

echo ""
echo "── 3. Optional Services ──"

for var in STRIPE_SECRET_KEY FAL_KEY SENTRY_DSN EBAY_CLIENT_ID FIRECRAWL_API_KEY; do
  val=$(eval echo "\${${var}:-}")
  if [ -n "$val" ] && [[ "$val" != *"placeholder"* ]]; then
    green "$var configured"
  else
    yellow "$var not configured (optional for beta)"
  fi
done

echo ""
echo "── 4. Connectivity Checks ──"

# Backend health
API_URL="${EXPO_PUBLIC_API_BASE_URL:-http://localhost:8000}"
if curl -sf --max-time 5 "$API_URL/healthz" > /dev/null 2>&1; then
  HEALTH=$(curl -sf --max-time 5 "$API_URL/healthz")
  green "Backend reachable at $API_URL/healthz"
  if echo "$HEALTH" | grep -q '"db":"up"'; then
    green "Database connection: UP"
  else
    red "Database connection: DOWN (check DB_DSN)"
  fi
else
  red "Backend unreachable at $API_URL/healthz"
  echo "  Is the server running? Try: curl $API_URL/healthz"
fi

# Supabase
SUPA_URL="${EXPO_PUBLIC_SUPABASE_URL:-}"
if [ -n "$SUPA_URL" ]; then
  if curl -sf --max-time 5 "$SUPA_URL/rest/v1/" -H "apikey: ${EXPO_PUBLIC_SUPABASE_ANON_KEY:-none}" > /dev/null 2>&1; then
    green "Supabase reachable at $SUPA_URL"
  else
    yellow "Supabase not reachable (may need anon key or network access)"
  fi
fi

echo ""
echo "── 5. Migration Files ──"

MIGRATION_COUNT=$(find migrations/ server/supabase/migrations/ -name "*.sql" 2>/dev/null | wc -l | tr -d ' ')
if [ "$MIGRATION_COUNT" -gt 0 ]; then
  green "$MIGRATION_COUNT migration files found"
else
  red "No migration files found"
fi

echo ""
echo "── 6. Build Configuration ──"

if [ -f "eas.json" ]; then
  green "eas.json found"
  if grep -q '"preview"' eas.json; then
    green "Preview build profile exists"
  else
    yellow "No 'preview' profile in eas.json"
  fi
else
  red "eas.json not found — run: eas init"
fi

if [ -f "app.json" ]; then
  if grep -q '"Atlantis"' app.json; then
    green "App name is 'Atlantis'"
  else
    yellow "App name not set to 'Atlantis' in app.json"
  fi
fi

echo ""
echo "═══════════════════════════════════════════════"
printf "  Results:  \033[32m%d passed\033[0m  " "$PASS"
printf "\033[31m%d failed\033[0m  " "$FAIL"
printf "\033[33m%d warnings\033[0m\n" "$WARN"
echo "═══════════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "  Fix the red items above before deploying."
  exit 1
else
  echo "  Ready for beta! Next steps:"
  echo "    1. Run migrations on Supabase"
  echo "    2. Deploy backend: docker build -t atlantis . && docker run ..."
  echo "    3. Seed catalog: cd server && python -m pipelines.import_all"
  echo "    4. Build app: npx eas build --profile preview --platform all"
  echo ""
  exit 0
fi
