#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_ANON_KEY:?}"
: "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

echo "[login] ${TEST_EMAIL}"
RESP="$(curl -sS "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")"

if ! echo "$RESP" | jq -e '.access_token' >/dev/null 2>&1; then
  echo "[error] login failed; raw response:"
  echo "$RESP"
  exit 1
fi

echo "$RESP" | jq -r '.access_token' > .jwt
size=$(wc -c < .jwt)
if [ "$size" -lt 100 ]; then
  echo "[error] access_token too short (${size} bytes):"
  echo "$RESP"
  exit 1
fi

echo "Wrote .jwt"
