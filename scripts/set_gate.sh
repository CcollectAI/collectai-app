#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_SERVICE_ROLE_KEY:?}"
NAME="${1:-price}"
ACTIVE="${2:-heuristic}"
CANDIDATE="${3:-}"
SPLIT="${4:-0}"
body='[{"name":"'"$NAME"'","active_version":"'"$ACTIVE"'","candidate_version":'\
$( [ -n "$CANDIDATE" ] && echo '"'$CANDIDATE'"' || echo null )',"candidate_split":'$SPLIT'}]'
curl -sS "${SUPABASE_URL}/rest/v1/model_gate?name=eq.${NAME}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -X PATCH -d "$body" | jq .
