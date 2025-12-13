#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_ANON_KEY:?}"
JWT="$(cat .jwt)"
title="${1:-Pikachu VMAX}"
category="${2:-Pokemon}"
cond="${3:-NM}"
ttl="${4:-180}"
curl -sS "${SUPABASE_URL}/functions/v1/predict-price" \
  -H "Authorization: Bearer ${JWT}" -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"title":"'"$title"'","category":"'"$category"'","attrs":{"condition":"'"$cond"'"},"ttl_sec":'"$ttl"'}' | jq .
