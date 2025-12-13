#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"
curl -sS "${SUPABASE_URL}/rest/v1/model_gate" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -H "Prefer: resolution=merge-duplicates" \
  -d '[{"name":"price","active_version":"heuristic","candidate_version":null,"candidate_split":0}]' >/dev/null
echo "Seeded model_gate price → heuristic"
