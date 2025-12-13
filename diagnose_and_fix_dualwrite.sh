#!/usr/bin/env bash
set -euo pipefail
[ -f ./supa_test.env ] || { echo "❌ supa_test.env missing"; exit 1; }
set -a; . ./supa_test.env; set +a

JWT="$(cat ./.jwt 2>/dev/null || true)"
[ -n "$JWT" ] || { echo "❌ Missing ./.jwt — run ./login_and_get_jwt.sh"; exit 1; }

# If you already have SUUID in the shell, we’ll use it; else we’ll fetch the latest for your tester.
if [[ -z "${SUUID:-}" || ! "$SUUID" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "→ Fetching latest session_uuid for your tester"
  USER_ID="$(./check_jwt.sh 2>/dev/null | sed -n '2,$p' | jq -r '.id')"
  SUUID="$(curl -sS \
    "https://${SUPA_REF}.supabase.co/rest/v1/predict_sessions?user_id=eq.${USER_ID}&select=uuid_id,created_at&order=created_at.desc&limit=1" \
    -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
    | jq -r '.[0].uuid_id')"
fi

echo "SUUID=${SUUID}"

echo
echo "→ predict_sessions row"
curl -sS \
  "https://${SUPA_REF}.supabase.co/rest/v1/predict_sessions?uuid_id=eq.${SUUID}&select=id,uuid_id,user_id,category,status,created_at" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" | jq .

echo
echo "→ label_events (latest 5)"
curl -sS \
  "https://${SUPA_REF}.supabase.co/rest/v1/label_events?select=session_uuid,corrected_title,created_at&order=created_at.desc&limit=5" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" | jq .

echo
echo "→ training_items for this UUID (before fix)"
curl -sS \
  "https://${SUPA_REF}.supabase.co/rest/v1/training_items?session_uuid=eq.${SUUID}&select=session_uuid,category,title,raw_title,raw_condition,raw_price_eur,corrected_title,corrected_condition,corrected_price_eur,created_at,updated_at" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" | jq .

echo
echo "→ Pinging predict-label again to force training upsert/insert (and echo row)"
curl -sS -w '\nHTTP %{http_code}\n' -X POST "https://${SUPA_REF}.supabase.co/functions/v1/predict-label" \
  -H "Content-Type: application/json" -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${JWT}" \
  --data-raw "{\"session_uuid\":\"${SUUID}\",\"corrected_title\":\"Pikachu Holo\",\"corrected_condition\":\"Near Mint\",\"corrected_price_eur\":189}" \
| tee /dev/stderr | sed -n '1p' | jq . 2>/dev/null || true

echo
echo "→ training_items for this UUID (after fix)"
curl -sS \
  "https://${SUPA_REF}.supabase.co/rest/v1/training_items?session_uuid=eq.${SUUID}&select=session_uuid,category,title,raw_title,raw_condition,raw_price_eur,corrected_title,corrected_condition,corrected_price_eur,created_at,updated_at" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" | jq .
