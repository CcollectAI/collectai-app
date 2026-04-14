#!/usr/bin/env bash
# Nightly automated health check for CollectAI infrastructure.
# Runs in GitHub Actions (nightly-sanity workflow) — sends Telegram alert on failure.
# Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, EC2_HOST (optional), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
set -euo pipefail

FAILURES=()
WARNINGS=()

fail() { FAILURES+=("$1"); echo "FAIL: $1"; }
warn() { WARNINGS+=("$1"); echo "WARN: $1"; }
pass() { echo "PASS: $1"; }

# ── 1. Required env vars ─────────────────────────────────────────────────
echo "=== ENV VAR CHECK ==="
for var in SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY TEST_EMAIL TEST_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    fail "Missing env var: $var"
  else
    pass "Env var $var is set"
  fi
done

# ── 2. Supabase Auth ─────────────────────────────────────────────────────
echo ""
echo "=== SUPABASE AUTH ==="
AUTH_RESP=$(curl -sS "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}" 2>&1) || true

if echo "$AUTH_RESP" | jq -e '.access_token' >/dev/null 2>&1; then
  JWT=$(echo "$AUTH_RESP" | jq -r '.access_token')
  pass "Supabase Auth login succeeded"
else
  fail "Supabase Auth login failed: $(echo "$AUTH_RESP" | head -c 200)"
  JWT=""
fi

# ── 3. DB row counts (via service role key) ───────────────────────────────
echo ""
echo "=== DB ROW COUNTS ==="
for table in category_items market_hits price_predictions; do
  COUNT=$(curl -sI "${SUPABASE_URL}/rest/v1/${table}?select=id" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Prefer: count=exact" \
    -H "Range: 0-0" 2>/dev/null | grep -i content-range | sed 's/.*\///;s/\r//')

  if [ -z "$COUNT" ] || [ "$COUNT" = "0" ]; then
    fail "$table has 0 or unknown rows"
  else
    pass "$table: $COUNT rows"
    # Threshold checks
    case $table in
      category_items)
        [ "$COUNT" -lt 100000 ] && warn "$table below 100K threshold ($COUNT)" ;;
      market_hits)
        [ "$COUNT" -lt 150000 ] && warn "$table below 150K threshold ($COUNT)" ;;
      price_predictions)
        [ "$COUNT" -lt 50000 ] && warn "$table below 50K threshold ($COUNT)" ;;
    esac
  fi
done

# ── 4. Valuation freshness — check latest prediction is < 24h old ─────────
echo ""
echo "=== VALUATION FRESHNESS ==="
LATEST_PRED=$(curl -sS "${SUPABASE_URL}/rest/v1/price_predictions?select=generated_at&order=generated_at.desc&limit=1" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null)

LATEST_TS=$(echo "$LATEST_PRED" | jq -r '.[0].generated_at // empty' 2>/dev/null || true)
if [ -z "$LATEST_TS" ]; then
  fail "No price_predictions found (valuation worker may be dead)"
else
  # Check if prediction is within last 24 hours
  LATEST_EPOCH=$(date -d "$LATEST_TS" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "$(echo "$LATEST_TS" | cut -c1-19)" +%s 2>/dev/null || echo "0")
  NOW_EPOCH=$(date +%s)
  AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))

  if [ "$AGE_HOURS" -gt 24 ]; then
    fail "Latest prediction is ${AGE_HOURS}h old (valuation worker stale)"
  elif [ "$AGE_HOURS" -gt 12 ]; then
    warn "Latest prediction is ${AGE_HOURS}h old"
  else
    pass "Latest prediction is ${AGE_HOURS}h old (fresh)"
  fi
fi

# ── 5. Market hits freshness — new hits in last 24h ──────────────────────
echo ""
echo "=== MARKET HITS FRESHNESS ==="
RECENT_HITS=$(curl -sI "${SUPABASE_URL}/rest/v1/market_hits?select=id&seen_at=gte.$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%S 2>/dev/null)" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Prefer: count=exact" \
  -H "Range: 0-0" 2>/dev/null | grep -i content-range | sed 's/.*\///;s/\r//')

if [ -z "$RECENT_HITS" ] || [ "$RECENT_HITS" = "0" ]; then
  warn "No new market_hits in last 24h (ingest may be stalled)"
else
  pass "$RECENT_HITS new market_hits in last 24h"
fi

# ── 6. EC2 health check (warning only — GH Actions can't reach private EC2) ──
echo ""
echo "=== EC2 HEALTH ==="
EC2_HOST="${EC2_HOST:-http://51.21.210.195:8000}"
EC2_HEALTH=$(curl -sS --connect-timeout 5 --max-time 10 "${EC2_HOST}/healthz" 2>&1) || true

if echo "$EC2_HEALTH" | jq -e '.ok == true' >/dev/null 2>&1; then
  DB_MS=$(echo "$EC2_HEALTH" | jq -r '.db_ms // "?"')
  pass "EC2 healthz OK (db_ms: ${DB_MS})"
else
  warn "EC2 healthz unreachable from CI (expected — private network): $(echo "$EC2_HEALTH" | head -c 120)"
fi

# ── 7. Event sources health (RSS feeds + APIs reachability) ──────────────
echo ""
echo "=== EVENT SOURCES ==="
# Fetch events count from last 24h to verify event scraper is working
EVENTS_24H=$(curl -sI "${SUPABASE_URL}/rest/v1/events?select=id&created_at=gte.$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%S 2>/dev/null)" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Prefer: count=exact" \
  -H "Range: 0-0" 2>/dev/null | grep -i content-range | sed 's/.*\///;s/\r//')

if [ -z "$EVENTS_24H" ] || [ "$EVENTS_24H" = "0" ]; then
  warn "No new events in last 24h (event scraper may be stalled)"
else
  pass "$EVENTS_24H new events in last 24h"
fi

# Total events count
EVENTS_TOTAL=$(curl -sI "${SUPABASE_URL}/rest/v1/events?select=id" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Prefer: count=exact" \
  -H "Range: 0-0" 2>/dev/null | grep -i content-range | sed 's/.*\///;s/\r//')

if [ -z "$EVENTS_TOTAL" ] || [ "$EVENTS_TOTAL" = "0" ]; then
  fail "events table is empty"
else
  pass "events total: $EVENTS_TOTAL rows"
  [ "$EVENTS_TOTAL" -lt 100 ] 2>/dev/null && warn "events total below 100 threshold"
fi

# ── 8. NULL item_ref check (catches the bug we fixed today) ──────────────
echo ""
echo "=== DATA INTEGRITY ==="
NULL_REFS=$(curl -sI "${SUPABASE_URL}/rest/v1/market_hits?select=id&item_ref=is.null&processed=is.false" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Prefer: count=exact" \
  -H "Range: 0-0" 2>/dev/null | grep -i content-range | sed 's/.*\///;s/\r//')

if [ -n "$NULL_REFS" ] && [ "$NULL_REFS" -gt 100 ] 2>/dev/null; then
  warn "$NULL_REFS unprocessed market_hits with NULL item_ref"
else
  pass "NULL item_ref check OK (${NULL_REFS:-0} unprocessed)"
fi

# ── Summary + Telegram alert ─────────────────────────────────────────────
echo ""
echo "=============================="
echo "FAILURES: ${#FAILURES[@]}"
echo "WARNINGS: ${#WARNINGS[@]}"
echo "=============================="

if [ "${#FAILURES[@]}" -gt 0 ]; then
  echo ""
  echo "Failed checks:"
  for f in "${FAILURES[@]}"; do echo "  - $f"; done
fi

if [ "${#WARNINGS[@]}" -gt 0 ]; then
  echo ""
  echo "Warnings:"
  for w in "${WARNINGS[@]}"; do echo "  - $w"; done
fi

# Send Telegram alert on failures (not warnings)
if [ "${#FAILURES[@]}" -gt 0 ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  MSG="🚨 *CollectAI Nightly Health Check FAILED*%0A%0A"
  MSG+="Failures: ${#FAILURES[@]}, Warnings: ${#WARNINGS[@]}%0A%0A"
  for f in "${FAILURES[@]}"; do MSG+="❌ ${f}%0A"; done
  for w in "${WARNINGS[@]}"; do MSG+="⚠️ ${w}%0A"; done
  MSG+="%0A$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=${MSG}" \
    -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  echo "Telegram alert sent"
fi

# Exit with failure code if any checks failed
[ "${#FAILURES[@]}" -eq 0 ]
