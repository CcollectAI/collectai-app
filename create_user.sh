#!/usr/bin/env bash
set -euo pipefail
: "${SUPA_REF:?} ${SERVICE_ROLE_KEY:?} ${TEST_EMAIL:?} ${TEST_PASSWORD:?}"

URL="https://${SUPA_REF}.supabase.co/auth/v1/admin/users"

RESP=$(curl -sS -w "\n%{http_code}" -X POST "$URL" \
  -H "apikey: ${SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  --data-raw "$(cat <<JSON
{
  "email": "${TEST_EMAIL}",
  "password": "${TEST_PASSWORD}",
  "email_confirm": true
}
JSON
)")
BODY=$(printf "%s" "$RESP" | sed '$d'); CODE=$(printf "%s" "$RESP" | tail -n1)
echo "Admin create user HTTP $CODE"
echo "$BODY"
# Accept created (200/201) or already exists (422)
if [ "$CODE" != "200" ] && [ "$CODE" != "201" ] && [ "$CODE" != "422" ]; then
  echo "❌ Failed to create/upsert user"; exit 1
fi
