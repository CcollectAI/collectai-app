#!/usr/bin/env bash
set -euo pipefail
set -a; . ./supa_test.env; set +a
AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"
ADMIN=(-H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" -H "Content-Type: application/json")

ENC_EMAIL="$(printf '%s' "$TEST_EMAIL" | sed 's/@/%40/g')"
RESP=$(curl -sS "${AUTH_URL}/admin/users?email=${ENC_EMAIL}" "${ADMIN[@]}")
USER_ID=$(printf '%s' "$RESP" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1 || true)

if [ -n "${USER_ID:-}" ]; then
  echo "→ Deleting existing user ${USER_ID}"
  curl -sS -w '\nHTTP %{http_code}\n' -X DELETE "${AUTH_URL}/admin/users/${USER_ID}" "${ADMIN[@]}"
else
  echo "→ No existing user"
fi

echo "→ Recreating user"
CREATE_JSON=$(printf '{"email":"%s","password":"%s","email_confirm":true}' "$TEST_EMAIL" "$TEST_PASSWORD")
curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/admin/users" "${ADMIN[@]}" --data-raw "$CREATE_JSON"

echo "→ Logging in"
curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")"
