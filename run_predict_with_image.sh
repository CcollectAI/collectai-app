#!/usr/bin/env bash
set -euo pipefail

# 0) Env + guards
[ -f ./supa_test.env ] || { echo "❌ supa_test.env missing"; exit 1; }
set -a; . ./supa_test.env; set +a
: "${SUPA_REF:?}"; : "${ANON_KEY:?}"

# Optional: pass IMAGE_URL via env or .env; empty is fine
IMAGE_URL="${IMAGE_URL:-}"

# 1) Ensure JWT
if [ ! -s ./.jwt ]; then
  echo "→ Getting a JWT (no ./.jwt found)…"
  ./login_and_get_jwt.sh >/dev/null || { echo "❌ could not get JWT"; exit 1; }
fi
JWT="$(cat ./.jwt)"

FN="https://${SUPA_REF}.functions.supabase.co"

call () {
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

# 2) Create session
CRE=$(call "predict-sessions" '{"category":"pokemon"}')
echo "$CRE" | grep -q 'HTTP 200' || { echo "❌ create failed"; exit 1; }
SID="$(printf '%s' "$CRE" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1)"
[ -n "${SID:-}" ] || { echo "❌ could not parse session id"; exit 1; }
echo "SID=$SID"

# 3) Complete (include image_url only if set)
if [ -n "$IMAGE_URL" ]; then
  COM=$(call "predict-complete" "$(jq -nc --argjson sid "$SID" --arg url "$IMAGE_URL" --argjson seed 0.72 \
    '{session_id:$sid, mock_seed:$seed, image_url:$url}')")
else
  COM=$(call "predict-complete" "$(jq -nc --argjson sid "$SID" --argjson seed 0.72 \
    '{session_id:$sid, mock_seed:$seed}')")
fi
echo "$COM" | grep -q 'HTTP 200' || { echo "❌ complete failed"; exit 1; }

# Try to read session_uuid from complete response; if absent, fallback to REST
SUUID="$(printf '%s' "$COM" | sed -n 's/.*"session_uuid":"\([^"]*\)".*/\1/p' | head -n1)"
if [ -z "$SUUID" ]; then
  echo "→ session_uuid not in complete response; fetching from REST…"
  : "${SERVICE_ROLE_KEY:?Set SERVICE_ROLE_KEY to use REST fallback}"
  SUUID="$(curl -sS "https://${SUPA_REF}.supabase.co/rest/v1/predict_sessions?id=eq.${SID}&select=uuid_id" \
    -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
    | jq -r '.[0].uuid_id')"
fi
[ -n "$SUUID" ] || { echo "❌ could not resolve session_uuid"; exit 1; }
echo "session_uuid=$SUUID"

# 4) Label (also include image_url if set)
if [ -n "$IMAGE_URL" ]; then
  LAB=$(call "predict-label" "$(jq -nc --arg su "$SUUID" --arg title "Pikachu Holo" --arg cond "Near Mint" --argjson price 189 --arg url "$IMAGE_URL" \
    '{session_uuid:$su, corrected_title:$title, corrected_condition:$cond, corrected_price_eur:$price, image_url:$url}')")
else
  LAB=$(call "predict-label" "$(jq -nc --arg su "$SUUID" --arg title "Pikachu Holo" --arg cond "Near Mint" --argjson price 189 \
    '{session_uuid:$su, corrected_title:$title, corrected_condition:$cond, corrected_price_eur:$price}')")
fi
echo "$LAB" | grep -q 'HTTP 200' || { echo "❌ label failed"; exit 1; }

echo
echo "✅ Done. Summary:"
echo "SID=$SID"
echo "SUUID=$SUUID"
echo "IMAGE_URL=${IMAGE_URL:-<none>}"
echo
echo "Label response:"
echo "$LAB" | sed -n '1,200p'
