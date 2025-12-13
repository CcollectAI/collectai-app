#!/usr/bin/env bash
set -euo pipefail

# Env
[ -f ./supa_test.env ] || { echo "❌ supa_test.env missing"; exit 1; }
set -a; . ./supa_test.env; set +a
: "${SUPA_REF:?}"; : "${ANON_KEY:?}"; : "${SERVICE_ROLE_KEY:?}"

# JWT
if [ ! -s ./.jwt ]; then
  echo "→ Getting JWT…"
  ./force_jwt_refresh.sh >/dev/null
fi
JWT="$(cat ./.jwt)"

FN="https://${SUPA_REF}.functions.supabase.co"

post () {
  local path="$1" json="$2"
  echo
  echo "→ POST $FN/$path"
  echo "↳ $json"
  curl -sS -w '\nHTTP %{http_code}\n' -X POST "$FN/$path" \
    -H "Content-Type: application/json" \
    -H "apikey: ${ANON_KEY}" \
    -H "Authorization: Bearer ${JWT}" \
    --data-raw "$json"
}

# 1) create
CRE=$(post "predict-sessions" '{"category":"pokemon"}')
echo "$CRE" | sed -n '1,200p'
echo "$CRE" | grep -q 'HTTP 200' || { echo "❌ create failed"; exit 1; }
SID="$(printf '%s' "$CRE" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1)"
[ -n "${SID:-}" ] || { echo "❌ no SID parsed"; exit 1; }
echo "SID=$SID"

# 2) REST check: does the row exist?
echo
echo "→ REST check (predict_sessions by id)"
PS=$(curl -sS "https://${SUPA_REF}.supabase.co/rest/v1/predict_sessions?id=eq.${SID}&select=id,uuid_id,user_id,category,created_at" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}")
echo "$PS" | jq .
COUNT=$(echo "$PS" | jq 'length')
if [ "$COUNT" -eq 0 ]; then
  echo "❌ predict_sessions has no row with id=$SID (create wrote somewhere else?)"
  exit 1
fi
SUUID="$(echo "$PS" | jq -r '.[0].uuid_id')"
echo "session_uuid (from REST) = $SUUID"

# 3) complete (include image_url only if $IMAGE_URL set)
if [ -n "${IMAGE_URL:-}" ]; then
  COM=$(post "predict-complete" "$(jq -nc --argjson sid "$SID" --arg url "$IMAGE_URL" --argjson seed 0.72 \
    '{session_id:$sid, mock_seed:$seed, image_url:$url}')")
else
  COM=$(post "predict-complete" "$(jq -nc --argjson sid "$SID" --argjson seed 0.72 \
    '{session_id:$sid, mock_seed:$seed}')")
fi
echo "$COM" | sed -n '1,200p'
echo "$COM" | grep -q 'HTTP 200' || { echo "❌ complete failed"; exit 1; }

# 4) parse session_uuid from complete (or fall back to REST value)
SUUID_BODY="$(printf '%s' "$COM" | sed -n 's/.*"session_uuid":"\([^"]*\)".*/\1/p' | head -n1 || true)"
echo "session_uuid (from complete)   = ${SUUID_BODY:-<none>}"
echo "session_uuid (authoritative)    = ${SUUID}"

echo
echo "✅ complete call succeeded"
