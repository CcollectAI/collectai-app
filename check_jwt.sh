#!/usr/bin/env bash
set -euo pipefail
set -a; . ./supa_test.env; set +a
: "${SUPA_REF:?}"; : "${ANON_KEY:?}"

JWT=$(cat ./.jwt 2>/dev/null || true)
[ -n "$JWT" ] || { echo "❌ Missing ./.jwt"; exit 1; }

URL="https://${SUPA_REF}.supabase.co/auth/v1/user"
RESP=$(curl -sS -w '\n%{http_code}\n' -X GET "$URL" \
  -H "apikey: ${ANON_KEY}" -H "Authorization: Bearer ${JWT}")
CODE="${RESP##*$'\n'}"; BODY="${RESP%$'\n'"$CODE"}"
[ "$CODE" = "200" ] || { echo "❌ JWT check failed (HTTP $CODE)"; echo "$BODY"; exit 1; }
echo "✅ JWT ok. User:"; echo "$BODY"
