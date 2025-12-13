#!/usr/bin/env bash
set -euo pipefail
: "${SUPABASE_URL:?}"; : "${SUPABASE_ANON_KEY:?}"

echo "[1/2] Checking GoTrue settings..."
curl -fsS "${SUPABASE_URL}/auth/v1/settings" \
  -H "apikey: ${SUPABASE_ANON_KEY}" -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "Accept: application/json" | jq '.external' >/dev/null && echo "OK: auth settings reachable"

echo "[2/2] Checking PostgREST root..."
curl -fsS "${SUPABASE_URL}/rest/v1/?select=1" \
  -H "apikey: ${SUPABASE_ANON_KEY}" -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "Accept: application/json" >/dev/null && echo "OK: rest reachable"
