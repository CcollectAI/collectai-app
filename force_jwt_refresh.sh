#!/usr/bin/env bash
set -euo pipefail

[ -f ./supa_test.env ] || { echo "❌ supa_test.env missing"; exit 1; }
set -a; . ./supa_test.env; set +a
: "${SUPA_REF:?}"; : "${ANON_KEY:?}"; : "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"

echo "→ Login via password grant (anon key)…"
LOGIN=$(curl -sS -X POST "${AUTH_URL}/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(jq -nc --arg e "$TEST_EMAIL" --arg p "$TEST_PASSWORD" '{email:$e,password:$p}')")

ACCESS=$(printf '%s' "$LOGIN" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' | head -n1)
[ -n "$ACCESS" ] || { echo "❌ Could not obtain JWT. Full response:"; echo "$LOGIN"; exit 1; }

printf '%s' "$ACCESS" > ./.jwt
echo "✅ Wrote ./.jwt (len: ${#ACCESS})"

echo "→ Verifying JWT…"
RESP=$(curl -sS -w '\n%{http_code}\n' -X GET "${AUTH_URL}/user" \
  -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${ACCESS}")
CODE="${RESP##*$'\n'}"; BODY="${RESP%$'\n'"$CODE"}"
[ "$CODE" = "200" ] || { echo "❌ JWT check failed ($CODE)"; echo "$BODY"; exit 1; }
echo "✅ JWT ok:"
echo "$BODY"
