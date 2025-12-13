#!/usr/bin/env bash
set -euo pipefail

# ========== Load env ==========
if [[ -f ./supa_test.env ]]; then
  set -a; . ./supa_test.env; set +a
else
  echo "❌ Missing supa_test.env"; exit 1
fi
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

# ========== Admin health ==========
echo "→ Admin check…"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "${AUTH_URL}/admin/users?per_page=1" "${ADMIN_HDR[@]}" | grep -q 'HTTP 200' \
  || { echo "❌ SERVICE_ROLE_KEY invalid for this project/ref (or wrong SUPA_REF)"; exit 1; }

# ========== Hard delete, then wait ==========
USER_ID="$(get_user_id || true)"
if [[ -n "${USER_ID:-}" ]]; then
  echo "→ Hard-deleting existing user ${USER_ID}"
  curl -sS -w "\nHTTP %{http_code}\n" -X DELETE \
    "${AUTH_URL}/admin/users/${USER_ID}?should_soft_delete=false" "${ADMIN_HDR[@]}"

  echo "→ Waiting for deletion to propagate…"
  for i in $(seq 1 30); do
    sleep 1
    USER_ID="$(get_user_id || true)"
    if [[ -z "${USER_ID:-}" ]]; then
      echo "  ✓ user fully gone after ${i}s"
      break
    fi
  done

  if [[ -n "${USER_ID:-}" ]]; then
    echo "⚠️  Still listed after wait; will proceed with create then fallback to password update."
  fi
fi

# ========== (Re)create user ==========
echo "→ Create user (email_confirm: true)…"
CREATE_JSON=$(printf '{"email":"%s","password":"%s","email_confirm":true}' "$TEST_EMAIL" "$TEST_PASSWORD")
CREATE_RESP=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/admin/users" "${ADMIN_HDR[@]}" --data-raw "$CREATE_JSON")
CR_CODE="${CREATE_RESP##*$'\n'}"; CR_BODY="${CREATE_RESP%$'\n'"$CR_CODE"}"
echo "  • Create response code: $CR_CODE"

if [[ "$CR_CODE" =~ ^HTTP\ 2 ]]; then
  USER_ID=$(printf '%s' "$CR_BODY" | sed -n 's/.*"id":"\([0-9a-fA-F-]\{36\}\)".*/\1/p' | head -n1)
  [[ -n "$USER_ID" ]] || { echo "❌ Create ok but no ID in body"; echo "$CR_BODY"; exit 1; }
  echo "  ✓ created user: $USER_ID"
else
  if echo "$CR_BODY" | grep -q '"email_exists"'; then
    echo "  ℹ️  email_exists — fetching existing user id and updating password…"
    USER_ID="$(get_user_id || true)"
    [[ -n "$USER_ID" ]] || { echo "❌ email_exists but could not fetch user id"; echo "$CR_BODY"; exit 1; }
  else
    echo "❌ Create failed: $CR_CODE"; echo "$CR_BODY"; exit 1
  fi
fi

# ========== Ensure password set (PATCH then PUT fallback) ==========
echo "→ Ensure password set & email confirmed…"
PATCH_JSON=$(printf '{"password":"%s","email_confirm":true}' "$TEST_PASSWORD")

echo "  • PATCH /admin/users/${USER_ID}"
PATCH_RESP=$(curl -sS -w '\nHTTP %{http_code}\n' -X PATCH "${AUTH_URL}/admin/users/${USER_ID}" "${ADMIN_HDR[@]}" --data-raw "$PATCH_JSON")
PR_CODE="${PATCH_RESP##*$'\n'}"; PR_BODY="${PATCH_RESP%$'\n'"$PR_CODE"}"
echo "    PATCH code: $PR_CODE"
if [[ ! "$PR_CODE" =~ ^HTTP\ 2 ]]; then
  if echo "$PR_CODE" | grep -q 'HTTP 405'; then
    echo "  • PATCH not allowed, trying PUT…"
    PUT_RESP=$(curl -sS -w '\nHTTP %{http_code}\n' -X PUT "${AUTH_URL}/admin/users/${USER_ID}" "${ADMIN_HDR[@]}" --data-raw "$PATCH_JSON")
    PU_CODE="${PUT_RESP##*$'\n'}"; PU_BODY="${PUT_RESP%$'\n'"$PU_CODE"}"
    echo "    PUT code: $PU_CODE"
    [[ "$PU_CODE" =~ ^HTTP\ 2 ]] || { echo "❌ Password update failed"; echo "$PU_BODY"; exit 1; }
  else
    echo "❌ Password update failed"; echo "$PR_BODY"; exit 1;
  fi
fi
echo "  ✓ password set"

# ========== Login (anon + password grant) ==========
echo "→ Login (anon + password grant)…"
rm -f ./.jwt 2>/dev/null || true
LOGIN_RESP=$(curl -sS -w '\nHTTP %{http_code}\n' -X POST "${AUTH_URL}/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" -H "Content-Type: application/json" \
  --data-raw "$(printf '{"email":"%s","password":"%s"}' "$TEST_EMAIL" "$TEST_PASSWORD")")
LR_CODE="${LOGIN_RESP##*$'\n'}"; LR_BODY="${LOGIN_RESP%$'\n'"$LR_CODE"}"
echo "  • Login code: $LR_CODE"
[[ "$LR_CODE" =~ ^HTTP\ 2 ]] || { echo "❌ Login failed"; echo "$LR_BODY"; exit 1; }

ACCESS=$(printf '%s' "$LR_BODY" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' | head -n1)
[[ -n "$ACCESS" ]] || { echo "❌ Login ok but no access_token in body"; echo "$LR_BODY"; exit 1; }
printf '%s' "$ACCESS" > ./.jwt
echo "  ✓ got JWT (len: ${#ACCESS})"

# ========== Verify & run E2E ==========
echo "→ Verifying JWT…"
./check_jwt.sh

echo "→ Running strict E2E…"
mkdir -p logs
./sanity_e2e_strict.sh 2>&1 | tee -a "logs/sanity_$(date +%F_%H%M%S).log"
