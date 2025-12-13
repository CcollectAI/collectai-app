#!/usr/bin/env bash
set -euo pipefail
set -a; . ./supa_test.env; set +a

JWT=$(cat ./.jwt 2>/dev/null || true)
[ -n "$JWT" ] || { echo "❌ Missing ./.jwt — run ./auth_hard_fix_and_run.sh"; exit 1; }

FN="https://${SUPA_REF}.functions.supabase.co"

echo "=== create ==="
C=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "$FN/predict-sessions" \
  -H "Content-Type: application/json" -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${JWT}" \
  --data-raw '{"category":"pokemon"}')
echo "$C" | sed -n '1,2p'
echo "$C" | grep -q 'HTTP 200' || exit 1
SID=$(printf '%s' "$C" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1)

echo
echo "=== complete ==="
P=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "$FN/predict-complete" \
  -H "Content-Type: application/json" -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${JWT}" \
  --data-raw "{\"session_id\": ${SID}, \"mock_seed\": 0.72}")
echo "$P" | sed -n '1,2p'
echo "$P" | grep -q 'HTTP 200' || exit 1
SUUID=$(printf '%s' "$P" | sed -n 's/.*"session_uuid":"\([^"]*\)".*/\1/p' | head -n1)

echo
echo "=== label ==="
L=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "$FN/predict-label" \
  -H "Content-Type: application/json" -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${JWT}" \
  --data-raw "{\"session_uuid\":\"${SUUID}\",\"corrected_title\":\"Pikachu Holo\",\"corrected_condition\":\"Near Mint\",\"corrected_price_eur\":189}")
echo "$L" | sed -n '1,2p'
echo "$L" | grep -q 'HTTP 200' || exit 1

echo
echo "=== training_items row (service role) ==="
curl -sS "https://${SUPA_REF}.supabase.co/rest/v1/training_items?session_uuid=eq.${SUUID}&select=session_uuid,user_id,category,raw_title,raw_condition,raw_price_eur,corrected_title,corrected_condition,corrected_price_eur,created_at,updated_at" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" | jq .
