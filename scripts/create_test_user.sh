#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"
: "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

redir() { tee /dev/stderr; }

echo "[check] looking up user: ${TEST_EMAIL}"
EXIST=$(curl -sS -w "\n%{http_code}" "${SUPABASE_URL}/auth/v1/admin/users?email=${TEST_EMAIL}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Accept: application/json")
BODY="$(echo "$EXIST" | sed '$d')"
CODE="$(echo "$EXIST" | tail -n1)"

if [ "$CODE" != "200" ]; then
  echo "[error] admin lookup failed ($CODE):"
  echo "$BODY" | redir
  exit 1
fi

if echo "$BODY" | jq -e '.[0].id' >/dev/null 2>&1; then
  USER_ID=$(echo "$BODY" | jq -r '.[0].id')
  echo "[ok] user exists: $USER_ID"
else
  echo "[create] creating user…"
  RES=$(curl -sS -w "\n%{http_code}" "${SUPABASE_URL}/auth/v1/admin/users" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -d @- <<JSON
{
  "email": "${TEST_EMAIL}",
  "password": "${TEST_PASSWORD}",
  "email_confirm": true
}
JSON
)
  RBODY="$(echo "$RES" | sed '$d')"
  RCODE="$(echo "$RES" | tail -n1)"
  if [ "$RCODE" != "200" ] && [ "$RCODE" != "201" ]; then
    echo "[error] admin create failed ($RCODE):"
    echo "$RBODY" | redir
    exit 1
  fi
  USER_ID=$(echo "$RBODY" | jq -r '.id')
  echo "[ok] created: $USER_ID"
fi

echo "[confirm] forcing email_confirm true…"
PATCH=$(curl -sS -w "\n%{http_code}" -X PATCH "${SUPABASE_URL}/auth/v1/admin/users/${USER_ID}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"email_confirm": true}')
PBODY="$(echo "$PATCH" | sed '$d')"
PCODE="$(echo "$PATCH" | tail -n1)"
if [ "$PCODE" != "200" ]; then
  echo "[warn] confirm returned ($PCODE):"
  echo "$PBODY" | redir
else
  echo "[ok] confirmed."
fi
