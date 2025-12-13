#!/usr/bin/env bash
set -euo pipefail
set -a; . ./supa_test.env; set +a

AUTH_URL="https://${SUPA_REF}.supabase.co/auth/v1"

echo "→ Checking anon key (public)…"
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "apikey: ${ANON_KEY}" \
  "${AUTH_URL}/health" | grep -qE '^(200|204)$' \
  && echo "  ✅ anon key looks OK" || { echo "  ❌ anon key invalid for this project"; exit 1; }

echo "→ Checking service role key (admin endpoint)…"
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "apikey: ${SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
  "${AUTH_URL}/admin/users?per_page=1" | grep -q '^200$' \
  && echo "  ✅ service role key OK" || { echo "  ❌ service role key invalid (wrong key or wrong project)"; exit 1; }
