#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"
: "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

QEMAIL="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$TEST_EMAIL")"

echo "[lookup] ${TEST_EMAIL}"
RES=$(curl -sS -w "\n%{http_code}" "${SUPABASE_URL}/auth/v1/admin/users?email=${QEMAIL}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Accept: application/json")

BODY="$(echo "$RES" | sed '$d')"
CODE="$(echo "$RES" | tail -n1)"
if [ "$CODE" != "200" ]; then
  echo "[error] lookup failed ($CODE): $BODY"; exit 1
fi

# Accept {id}, [{id}], or {users:[{id}]}
USER_ID="$(echo "$BODY" | jq -r 'try .id // empty')"
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
  USER_ID="$(echo "$BODY" | jq -r 'try .[0].id // empty')"
fi
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
  USER_ID="$(echo "$BODY" | jq -r 'try .users[0].id // empty')"
fi
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
  echo "[error] user not found in response:"; echo "$BODY"; exit 1
fi

echo "[ok] user id: $USER_ID"
echo "[patch] setting new password + confirming email…"

PATCH=$(curl -sS -w "\n%{http_code}" -X PATCH "${SUPABASE_URL}/auth/v1/admin/users/${USER_ID}" \
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
PBODY="$(echo "$PATCH" | sed '$d')"
PCODE="$(echo "$PATCH" | tail -n1)"
if [ "$PCODE" != "200" ]; then
  echo "[error] patch failed ($PCODE): $PBODY"; exit 1
fi

echo "[ok] password reset & email confirmed."
