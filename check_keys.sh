#!/usr/bin/env bash
set -euo pipefail
: "${SUPA_REF:?} ${ANON_KEY:?} ${SERVICE_ROLE_KEY:?}"

BASE="https://${SUPA_REF}.supabase.co"

echo "== Check 1: anon key on public auth settings (expect HTTP 200) =="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "apikey: ${ANON_KEY}" \
  "${BASE}/auth/v1/settings"

echo "== Check 2: service-role key on admin users (expect HTTP 200) =="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "apikey: ${SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
  "${BASE}/auth/v1/admin/users?per_page=1"

echo "== Decode headers/payloads (inspect iss & role) =="
decode_jwt() {
  tok="$1"
  IFS='.' read -r h p s <<<"$tok" || true
  printf "%s" "$h" | tr '_-' '/+' | base64 -d 2>/dev/null || true; echo
  printf "%s" "$p" | tr '_-' '/+' | base64 -d 2>/dev/null || true; echo
  echo "---"
}
echo "-- anon key --"; decode_jwt "$ANON_KEY"
echo "-- service_role key --"; decode_jwt "$SERVICE_ROLE_KEY"
echo "Tip: payload.iss should include '${SUPA_REF}.supabase.co/auth/v1', and 'role' should be 'anon' vs 'service_role'."
