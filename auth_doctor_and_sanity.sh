#!/usr/bin/env bash
set -euo pipefail

# --- Load env (must exist) ---
if [[ -f ./supa_test.env ]]; then
  set -a; . ./supa_test.env; set +a
else
  echo "❌ Missing supa_test.env"; exit 1
fi

# --- Guards for required vars ---
: "${SUPA_REF:?SUPA_REF missing}"
: "${ANON_KEY:?ANON_KEY missing}"
: "${SERVICE_ROLE_KEY:?SERVICE_ROLE_KEY missing}"
: "${TEST_EMAIL:?TEST_EMAIL missing}"
: "${TEST_PASSWORD:?TEST_PASSWORD missing}"

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"
HDR_ADMIN=(-H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" -H "Content-Type: application/json")

echo "→ Checking admin access…"
curl -sS "${AUTH_URL}/admin/users?per_page=1" "${HDR_ADMIN[@]}" >/dev/null \
  || { echo "❌ SERVICE_ROLE_KEY invalid for this project (or wrong SUPA_REF)"; exit 1; }

# Percent-encode email for the query string
ENC_EMAIL="$(printf '%s' "$TEST_EMAIL" | sed 's/@/%40/g')"

echo "→ Ensuring test user exists: ${TEST_EMAIL}"
RESP=$(curl -sS "${AUTH_URL}/admin/users?email=${ENC_EMAIL}" "${HDR_ADMIN[@]}")
USER_ID=$(printf '%s' "$RESP" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1 || true)

if [[ -z "${USER_ID:-}" ]]; then
  echo "→ Creating & confirming user…"
  CREATE_JSON=$(printf '{"email":"%s","password":"%s","email_confirm":true}' "$TEST_EMAIL" "$TEST_PASSWORD")
  R=$(curl -sS -w '\n%{http_code}' -X POST "${AUTH_URL}/admin/users" "${HDR_ADMIN[@]}" --data-raw "$CREATE_JSON")
  CODE="${R##*$'\n'}"; BODY="${R%$'\n'"$CODE"}"
  [[ "$CODE" =~ ^2 ]] || { echo "❌ Create failed ($CODE): $BODY"; exit 1; }
  USER_ID=$(printf '%s' "$BODY" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1)
  [[ -n "$USER_ID" ]] || { echo "❌ Create ok but no ID in body: $BODY"; exit 1; }
  echo "✅ Created user: $USER_ID"
else
  echo "✅ Found user: $USER_ID"
fi

echo "→ Setting password & confirming email…"
PATCH_JSON=$(printf '{"password":"%s","email_confirm":true}' "$TEST_PASSWORD")
R=$(curl -sS -w '\n%{http_code}' -X PATCH "${AUTH_URL}/admin/users/${USER_ID}" "${HDR_ADMIN[@]}" --data-raw "$PATCH_JSON")
CODE="${R##*$'\n'}"; BODY="${R%$'\n'"$CODE"}"
[[ "$CODE" =~ ^2 ]] || { echo "❌ Password update failed ($CODE): $BODY"; exit 1; }
echo "✅ Password set (HTTP $CODE)"

# Always clear any stale token before login
rm -f ./.jwt 2>/dev/null || true

echo "→ Logging in (anon key + password grant)…"
AUTH_TOKEN_URL="${AUTH_URL}/token?grant_type=password"
LOGIN=$(curl -sS -w '\n%{http_code}' -X POST "$AUTH_TOKEN_URL" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")")

LCODE="${LOGIN##*$'\n'}"; LBODY="${LOGIN%$'\n'"$LCODE"}"
[[ "$LCODE" =~ ^2 ]] || { echo "❌ Could not obtain JWT ($LCODE): $LBODY"; exit 1; }

ACCESS=$(printf '%s' "$LBODY" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' | head -n1)
[[ -n "$ACCESS" ]] || { echo "❌ Login ok but no access_token in body: $LBODY"; exit 1; }
printf '%s' "$ACCESS" > ./.jwt
echo "✅ Got JWT (length: ${#ACCESS})"

echo "→ Verifying JWT…"
./check_jwt.sh

echo "→ Running strict E2E…"
mkdir -p logs
./sanity_e2e_strict.sh 2>&1 | tee -a "logs/sanity_$(date +%F_%H%M%S).log"
