#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_ANON_KEY:?}"

JWT="$(cat .jwt)"
IDEM_KEY="${IDEM_KEY:-calai-demo-1}"

echo "Checking training_items idem_key=${IDEM_KEY}"
curl -sS "${SUPABASE_URL}/rest/v1/training_items?idem_key=eq.${IDEM_KEY}&select=idem_key,title,version,source,image_url,attributes" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Authorization: Bearer ${JWT}" \
  -H "Accept: application/json" | jq .
