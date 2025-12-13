#!/usr/bin/env bash
set -euo pipefail
set -a; . ./supa_test.env; set +a

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"
ADMIN=(-H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" -H "Content-Type: application/json")

echo "→ Admin list 1 user (should be 200):"
curl -sS -w '\nHTTP %{http_code}\n' "${AUTH_URL}/admin/users?per_page=1" "${ADMIN[@]}"

ENC_EMAIL="$(printf '%s' "$TEST_EMAIL" | sed 's/@/%40/g')"
echo; echo "→ Lookup test user:"
curl -sS -w '\nHTTP %{http_code}\n' "${AUTH_URL}/admin/users?email=${ENC_EMAIL}" "${ADMIN[@]}"

echo; echo "→ Create (safe to run; will 400 if exists):"
CREATE_JSON=$(printf '{"email":"%s","password":"%s","email_confirm":true}' "$TEST_EMAIL" "$TEST_PASSWORD")
curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/admin/users" "${ADMIN[@]}" --data-raw "$CREATE_JSON"

echo; echo "→ Force password set (PATCH should be 200/204):"
# Get id again
RESP=$(curl -sS "${AUTH_URL}/admin/users?email=${ENC_EMAIL}" "${ADMIN[@]}")
USER_ID=$(printf '%s' "$RESP" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1 || true)
if [ -z "${USER_ID:-}" ]; then echo "No USER_ID found; aborting."; exit 1; fi
PATCH_JSON=$(printf '{"password":"%s","email_confirm":true}' "$TEST_PASSWORD")
curl -sS -w '\nHTTP %{http_code}\n' -X PATCH "${AUTH_URL}/admin/users/${USER_ID}" "${ADMIN[@]}" --data-raw "$PATCH_JSON"

echo; echo "→ Login with anon (password grant; should be 200):"
curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")"
