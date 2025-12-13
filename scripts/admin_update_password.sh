#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"
: "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

QEMAIL="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$TEST_EMAIL")"

# Lookup user id
RES=$(curl -sS -w "\n%{http_code}" "${SUPABASE_URL}/auth/v1/admin/users?email=${QEMAIL}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Accept: application/json")
BODY="$(echo "$RES" | sed '$d')"
CODE="$(echo "$RES" | tail -n1)"
[ "$CODE" = "200" ] || { echo "[error] lookup $CODE: $BODY"; exit 1; }

USER_ID="$(echo "$BODY" | jq -r 'try .id // empty | select(.!="")')"
[ -n "$USER_ID" ] || USER_ID="$(echo "$BODY" | jq -r 'try .[0].id // empty | select(.!="")')"
[ -n "$USER_ID" ] || USER_ID="$(echo "$BODY" | jq -r 'try .users[0].id // empty | select(.!="")')"
[ -n "$USER_ID" ] || { echo "[error] no user id in: $BODY"; exit 1; }

echo "[info] user id: $USER_ID"

# 1) Try PUT (some GoTrue setups allow PUT but not PATCH)
PUT_RES=$(curl -sS -w "\n%{http_code}" -X PUT "${SUPABASE_URL}/auth/v1/admin/users/${USER_ID}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "password": "${TEST_PASSWORD}",
  "email_confirm": true
}
JSON
)
PUT_BODY="$(echo "$PUT_RES" | sed '$d')"
PUT_CODE="$(echo "$PUT_RES" | tail -n1)"

if [ "$PUT_CODE" = "200" ]; then
  echo "[ok] password set via PUT."
  exit 0
fi

echo "[warn] PUT returned $PUT_CODE; body:"
echo "$PUT_BODY"

# 2) Fallback to PATCH again (in case PUT is blocked but PATCH allowed)
PATCH_RES=$(curl -sS -w "\n%{http_code}" -X PATCH "${SUPABASE_URL}/auth/v1/admin/users/${USER_ID}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "password": "${TEST_PASSWORD}",
  "email_confirm": true
}
JSON
)
PATCH_BODY="$(echo "$PATCH_RES" | sed '$d')"
PATCH_CODE="$(echo "$PATCH_RES" | tail -n1)"

if [ "$PATCH_CODE" = "200" ]; then
  echo "[ok] password set via PATCH."
  exit 0
fi

echo "[error] both PUT ($PUT_CODE) and PATCH ($PATCH_CODE) failed."
echo "PUT body:   $PUT_BODY"
echo "PATCH body: $PATCH_BODY"
exit 1
