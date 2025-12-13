#!/usr/bin/env bash
set -euo pipefail

# auto-load env
if [[ -f ./supa_test.env ]]; then set -a; . ./supa_test.env; set +a; fi
: "${SUPA_REF:?}"; : "${ANON_KEY:?}"

JWT=$(cat ./.jwt 2>/dev/null || true)
[ -n "$JWT" ] || { echo "❌ Missing ./.jwt — run auth script"; exit 1; }

FN="https://${SUPA_REF}.functions.supabase.co"

call () {
  local url="$1" data="$2"
  echo "→ POST $url"
  RESP=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "$url" \
    -H "Content-Type: application/json" \
    -H "apikey: ${ANON_KEY}" \
    -H "Authorization: Bearer ${JWT}" \
    --data-raw "$data")
  echo "$RESP"
}

echo "=== 1) create ==="
C=$(call "${FN}/predict-sessions" '{"category":"pokemon"}')
echo "$C" | grep -q 'HTTP 200' || { echo "❌ Create failed"; exit 1; }
SID=$(printf '%s' "$C" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1)
[ -n "$SID" ] || { echo "❌ No session id in create response"; exit 1; }

echo
echo "=== 2) complete ==="
P=$(call "${FN}/predict-complete" "{\"session_id\": ${SID}, \"mock_seed\": 0.72}")
echo "$P" | grep -q 'HTTP 200' || { echo "❌ Complete failed"; exit 1; }
SUUID=$(printf '%s' "$P" | sed -n 's/.*"session_uuid":"\([0-9a-fA-F-]\{8\}-[0-9a-fA-F-]\{4\}-[0-9a-fA-F-]\{4\}-[0-9a-fA-F-]\{4\}-[0-9a-fA-F-]\{12\}\)".*/\1/p' | head -n1)
[ -n "$SUUID" ] || { echo "❌ No session_uuid in complete response (ensure predict-complete returns it)"; exit 1; }

echo
echo "=== 3) label (UUID-only) ==="
L=$(call "${FN}/predict-label" "{\"session_uuid\": \"${SUUID}\", \"corrected_title\": \"Pikachu Holo\", \"corrected_condition\": \"Near Mint\", \"corrected_price_eur\": 189}")
echo "$L" | grep -q 'HTTP 200' || { echo "❌ Label failed"; exit 1; }
echo "✅ E2E passed"
