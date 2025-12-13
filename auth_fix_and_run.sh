#!/usr/bin/env bash
set -euo pipefail

# Load env
if [[ -f ./supa_test.env ]]; then set -a; . ./supa_test.env; set +a; else
  echo "❌ Missing supa_test.env"; exit 1; fi

: "${SUPA_REF:?}"; : "${ANON_KEY:?}"; : "${SERVICE_ROLE_KEY:?}"
: "${TEST_EMAIL:?}"; : "${TEST_PASSWORD:?}"

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"
ADMIN_HDR=(-H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" -H "Content-Type: application/json")

urlenc() { printf '%s' "$1" | sed -e 's/%/%25/g' -e 's/@/%40/g' -e 's/+/%2B/g'; }
ENC_EMAIL="$(urlenc "$TEST_EMAIL")"

get_user_json() {
  curl -sS "${AUTH_URL}/admin/users?email=${ENC_EMAIL}" "${ADMIN_HDR[@]}"
}
get_user_id() {
  get_user_json | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1
}

echo "→ Admin check…"
curl -sS -o /dev/null -w "%{http_code}\n" "${AUTH_URL}/admin/users?per_page=1" "${ADMIN_HDR[@]}" | grep -q '^200$' || {
  echo "❌ SERVICE_ROLE_KEY invalid for this project/ref"; exit 1; }

USER_ID="$(get_user_id || true)"
if [[ -n "${USER_ID:-}" ]]; then
  echo "→ Hard-deleting existing user ${USER_ID}"
  # HARD DELETE so email is really freed
  curl -sS -o /dev/null -w "%{http_code}\n" -X DELETE \
    "${AUTH_URL}/admin/users/${USER_ID}?should_soft_delete=false" "${ADMIN_HDR[@]}" | grep -q '^200$' || {
      echo "❌ Hard delete failed"; exit 1; }

  echo "→ Waiting for deletion to propagate…"
  tries=0
  while [[ $tries -lt 30 ]]; do
    sleep 1
    USER_ID="$(get_user_id || true)"
    if [[ -z "${USER_ID:-}" ]]; then
      echo "  ✓ user fully gone"
      break
    fi
    tries=$((tries+1))
  done
  if [[ -n "${USER_ID:-}" ]]; then
    echo "⚠️  Still present after wait; will attempt create-then-fallback-to-patch."
  fi
fi

echo "→ Create user (email_confirm: true)…"
CREATE_JSON=$(printf '{"email":"%s","password":"%s","email_confirm":true}' "$TEST_EMAIL" "$TEST_PASSWORD")
CREATE_RESP=$(curl -sS -w '\n%{http_code}' -X POST "${AUTH_URL}/admin/users" "${ADMIN_HDR[@]}" --data-raw "$CREATE_JSON")
CR_CODE="${CREATE_RESP##*$'\n'}"; CR_BODY="${CREATE_RESP%$'\n'"$CR_CODE"}"

if [[ "$CR_CODE" =~ ^2 ]]; then
  echo "  ✓ created (HTTP $CR_CODE)"
  USER_ID=$(printf '%s' "$CR_BODY" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1)
else
  # If email still exists, fetch id and proceed with patch
  if echo "$CR_BODY" | grep -q '"email_exists"'; then
    echo "  ℹ️  email_exists — fetching existing user id and patching password…"
    USER_ID="$(get_user_id || true)"
    if [[ -z "${USER_ID:-}" ]]; then
      echo "❌ email_exists but could not fetch user id; body: $CR_BODY"; exit 1
    fi
  else
    echo "❌ Create failed ($CR_CODE): $CR_BODY"; exit 1
  fi
fi

# At this point we must have USER_ID
if [[ -z "${USER_ID:-}" ]]; then echo "❌ No USER_ID after create/lookup"; exit 1; fi

echo "→ Ensure password set & email confirmed…"
PATCH_JSON=$(printf '{"password":"%s","email_confirm":true}' "$TEST_PASSWORD")
PATCH_RESP=$(curl -sS -w '\n%{http_code}' -X PATCH "${AUTH_URL}/admin/users/${USER_ID}" "${ADMIN_HDR[@]}" --data-raw "$PATCH_JSON")
PR_CODE="${PATCH_RESP##*$'\n'}"
[[ "$PR_CODE" =~ ^2 ]] || { echo "❌ Password update failed ($PR_CODE): ${PATCH_RESP%$'\n'"$PR_CODE"}"; exit 1; }
echo "  ✓ password set (HTTP $PR_CODE)"

# Clear any stale token
rm -f ./.jwt 2>/dev/null || true

echo "→ Login (anon + password grant)…"
LOGIN_RESP=$(curl -sS -w '\n%{http_code}' -X POST "${AUTH_URL}/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")")
LR_CODE="${LOGIN_RESP##*$'\n'}"; LR_BODY="${LOGIN_RESP%$'\n'"$LR_CODE"}"
[[ "$LR_CODE" =~ ^2 ]] || { echo "❌ Login failed ($LR_CODE): $LR_BODY"; exit 1; }
ACCESS=$(printf '%s' "$LR_BODY" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' | head -n1)
[[ -n "$ACCESS" ]] || { echo "❌ Login ok but no access_token in body: $LR_BODY"; exit 1; }
printf '%s' "$ACCESS" > ./.jwt
echo "  ✓ got JWT (len: ${#ACCESS})"

echo "→ Verify JWT payload…"
./check_jwt.sh

echo "→ Run strict E2E…"
mkdir -p logs
./sanity_e2e_strict.sh 2>&1 | tee -a "logs/sanity_$(date +%F_%H%M%S).log"
