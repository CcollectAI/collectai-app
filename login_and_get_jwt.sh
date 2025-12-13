#!/usr/bin/env bash
set -euo pipefail
[ -f ./supa_test.env ] || { echo "❌ supa_test.env missing"; exit 1; }
set -a; . ./supa_test.env; set +a

: "${SUPA_REF:?}"; : "${ANON_KEY:?}"; : "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"
AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1/token?grant_type=password"

RESP=$(curl -sS -X POST "$AUTH_URL" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")")

ACCESS=$(printf '%s' "$RESP" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' | head -n1)
[ -n "$ACCESS" ] || { echo "❌ Login failed:\n$RESP"; exit 1; }
printf '%s' "$ACCESS" > ./.jwt
echo "✅ Wrote ./.jwt (len: ${#ACCESS})"

# (Optional) print expiry
EXP=$(printf '%s' "$ACCESS" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | sed -n 's/.*"exp":\([0-9]*\).*/\1/p')
[ -n "${EXP:-}" ] && date -d "@$EXP" +"ℹ️  JWT expires at: %Y-%m-%d %H:%M:%S %Z" 2>/dev/null || true
