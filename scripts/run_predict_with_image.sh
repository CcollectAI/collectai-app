#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_ANON_KEY:?}"
JWT="$(cat .jwt)"
API="${SUPABASE_URL}/functions/v1"

IDEM_KEY="${IDEM_KEY:-calai-demo-1}"
CATEGORY="${CATEGORY:-Pokemon}"
TITLE="${TITLE:-Pikachu VMAX}"

# 1) create session
SESSION_JSON=$(curl -sS "${API}/predict-sessions" \
  -H "Authorization: Bearer ${JWT}" -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"collectai\",\"version\":\"v1\",\"category\":\"${CATEGORY}\",\"meta\":{\"env\":\"dev\"},\"idem_key\":\"${IDEM_KEY}\"}")
echo "Session resp: $SESSION_JSON"
SESSION_ID=$(echo "$SESSION_JSON" | jq -r '.session.id // empty')
[ -n "$SESSION_ID" ] || { echo "No session_id returned"; exit 1; }
echo "Session: $SESSION_ID"

# 2) complete
COMPLETE_JSON=$(curl -sS "${API}/predict-complete" \
  -H "Authorization: Bearer ${JWT}" -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "session_id": "$SESSION_ID",
  "output": { "title": "${TITLE}", "category": "${CATEGORY}", "predicted_value_eur": 42.5 },
  "image_url": "https://example.com/pikachu.jpg",
  "source": "collectai",
  "version": "v1",
  "idem_key": "${IDEM_KEY}"
}
JSON
)
echo "Complete: $COMPLETE_JSON"

# 3) label
LABEL_JSON=$(curl -sS "${API}/predict-label" \
  -H "Authorization: Bearer ${JWT}" -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "session_id": "$SESSION_ID",
  "corrections": { "title": "${TITLE} (Rainbow)", "condition":"NM", "category":"${CATEGORY}", "final_value_eur": 55.00 },
  "image_url": "https://example.com/pikachu.jpg",
  "source": "collectai",
  "version": "v1",
  "idem_key": "${IDEM_KEY}"
}
JSON
)
echo "Label: $LABEL_JSON"
