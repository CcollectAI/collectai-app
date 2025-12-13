#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"; : "${TEST_EMAIL:?}"

QEMAIL="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$TEST_EMAIL")"

curl -sS "${SUPABASE_URL}/auth/v1/admin/users?email=${QEMAIL}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Accept: application/json" | jq .
