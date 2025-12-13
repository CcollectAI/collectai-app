#!/usr/bin/env bash
set -euo pipefail

# Load env
if [[ -f ./supa_test.env ]]; then set -a; . ./supa_test.env; set +a; fi
: "${SUPA_REF:?}"; : "${SERVICE_ROLE_KEY:?}"; : "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"

hdr=(-H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" -H "Content-Type: application/json")

echo "→ Looking up user: ${TEST_EMAIL}"
RESP=$(curl -sS "${AUTH_URL}/admin/users?email=${TEST_EMAIL}" "${hdr[@]}")

# Try to extract first user id if present
USER_ID=$(printf '%s' "$RESP" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1 || true)

if [[ -z "${USER_ID:-}" ]]; then
  echo "→ User not found. Creating & confirming…"
  CREATE_PAYLOAD=$(cat <<JSON
{"email":"${TEST_EMAIL}","password":"${TEST_PASSWORD}","email_confirm":true}
JSON
)
  CREATE_RESP=$(curl -sS -X POST "${AUTH_URL}/admin/users" "${hdr[@]}" --data-raw "${CREATE_PAYLOAD}")
  echo "$CREATE_RESP" | grep -q '"id":"' || { echo "❌ Create failed: $CREATE_RESP"; exit 1; }
  USER_ID=$(printf '%s' "$CREATE_RESP" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1)
  echo "✅ Created user: $USER_ID"
else
  echo "✅ Found user: $USER_ID"
fi

echo "→ Updating password…"
PATCH_PAYLOAD=$(cat <<JSON
{"password":"${TEST_PASSWORD}","email_confirm":true}
JSON
)
PATCH_RESP=$(curl -sS -X PATCH "${AUTH_URL}/admin/users/${USER_ID}" "${hdr[@]}" --data-raw "${PATCH_PAYLOAD}")
echo "$PATCH_RESP" | grep -q '"id":"' || { echo "❌ Password update failed: $PATCH_RESP"; exit 1; }
echo "✅ Password set & email confirmed for ${TEST_EMAIL}"
