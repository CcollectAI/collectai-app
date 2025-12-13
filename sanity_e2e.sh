#!/usr/bin/env bash
set -euo pipefail
: "${SUPA_REF:?}"
JWT=$(cat .jwt 2>/dev/null || true)
[ -n "$JWT" ] || { echo "❌ Missing ./.jwt (run login_and_get_jwt.sh)"; exit 1; }
FN="https://${SUPA_REF}.functions.supabase.co"

CREATE_OUT=$(curl -sS -X POST "${FN}/predict-sessions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT}" \
  --data-raw '{"category":"pokemon"}')
echo "CREATE_OUT=$CREATE_OUT"
SESSION_ID=$(printf '%s' "$CREATE_OUT" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -n1)
[ -n "$SESSION_ID" ] || { echo "❌ SESSION_ID not found"; exit 1; }
echo "✅ SESSION_ID=$SESSION_ID"

COMPLETE_OUT=$(curl -sS -X POST "${FN}/predict-complete" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT}" \
  --data-raw "{\"session_id\":\"${SESSION_ID}\",\"mock_seed\":0.72}")
echo "COMPLETE_OUT=$COMPLETE_OUT"
echo "$COMPLETE_OUT" | grep -q '"status":"done"' && echo "✅ Completed" || { echo "❌ Complete failed"; exit 1; }

LABEL_OUT=$(curl -sS -X POST "${FN}/predict-label" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT}" \
  --data-raw "{\"session_id\":\"${SESSION_ID}\",\"corrected_title\":\"Pikachu Holo\",\"corrected_condition\":\"Near Mint\",\"corrected_price_eur\":189}")
echo "LABEL_OUT=$LABEL_OUT"
echo "$LABEL_OUT" | grep -q '"label":' && echo "✅ Label saved" || { echo "❌ Label failed"; exit 1; }
