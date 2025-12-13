#!/usr/bin/env bash
set -euo pipefail

echo "=== env check ==="
echo "SUPABASE_URL              = ${SUPABASE_URL:-"(unset)"}"
echo "SUPABASE_ANON_KEY         = ${SUPABASE_ANON_KEY:+(set)}"
echo "SUPABASE_SERVICE_ROLE_KEY = ${SUPABASE_SERVICE_ROLE_KEY:+(set)}"
echo

if [ -z "${SUPABASE_URL:-}" ]; then
  echo "❌ SUPABASE_URL is unset. Run:  set -a; source supa_test.env; set +a"
  exit 1
fi

# 1) URL shape sanity (must be https://<project-ref>.supabase.co — NOT a dashboard URL)
echo "=== url shape ==="
if [[ "$SUPABASE_URL" =~ ^https://[a-z0-9]{20}\.supabase\.co$ ]]; then
  echo "✔ URL looks like a project endpoint"
else
  echo "⚠ URL looks unusual. Expected: https://<project-ref>.supabase.co"
  echo "   Example for your project: https://ykqrruipzmrrvjcvwfgp.supabase.co"
fi
echo

# 2) REST reachability (service key)
if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "⚠ SERVICE_ROLE_KEY not set; skipping admin checks."
else
  echo "=== rest (service role) ==="
  code=$(curl -sS -o /dev/null -w "%{http_code}" \
    "$SUPABASE_URL/rest/v1/?select=1" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Accept: application/json") || true
  echo "REST /v1/?select=1 -> HTTP $code (expected 200 or 404)"
  [ "$code" = "200" ] || [ "$code" = "404" ] || echo "❌ REST not reachable with service role"
  echo
fi

# 3) Auth health (no auth needed)
echo "=== auth health ==="
code=$(curl -sS -o /dev/null -w "%{http_code}" "$SUPABASE_URL/auth/v1/health") || true
echo "/auth/v1/health -> HTTP $code (expected 200)"
[ "$code" = "200" ] || echo "❌ Auth health not OK"
echo

# 4) Functions ping (anon key)
if [ -z "${SUPABASE_ANON_KEY:-}" ]; then
  echo "⚠ ANON key not set; skipping function ping."
else
  echo "=== functions (OPTIONS ping) ==="
  code=$(curl -sS -o /dev/null -w "%{http_code}" -X OPTIONS \
    "$SUPABASE_URL/functions/v1/" \
    -H "apikey: $SUPABASE_ANON_KEY") || true
  echo "/functions/v1/ (OPTIONS) -> HTTP $code (200/204/404 acceptable)"
  echo
fi

# 5) JWT login sanity (client flow using anon key)
if [ -f ".jwt" ]; then rm -f .jwt; fi
if [ -f "./scripts/force_jwt_refresh.sh" ] && [ -n "${SUPABASE_ANON_KEY:-}" ]; then
  echo "=== login flow ==="
  set +e
  ./scripts/force_jwt_refresh.sh
  rc=$?
  set -e
  if [ $rc -ne 0 ] || [ ! -s ./.jwt ]; then
    echo "❌ Could not fetch JWT via force_jwt_refresh.sh (check TEST_EMAIL/TEST_PASSWORD and anon key)"
  else
    echo "✔ JWT ok"
    JWT=$(cat .jwt)
    # ping a known function if present
    if curl -sS "$SUPABASE_URL/functions/v1/predict-price" \
      -H "Authorization: Bearer $JWT" -H "apikey: $SUPABASE_ANON_KEY" \
      -H "Content-Type: application/json" \
      -d '{"title":"Ping","category":"Pokemon","attrs":{"condition":"NM"},"ttl_sec":30}' >/dev/null; then
      echo "✔ predict-price reachable with client JWT"
    else
      echo "⚠ predict-price ping failed (check function deploy and headers)"
    fi
  fi
fi

echo
echo "=== verdict hints ==="
echo "- If Auth health fails: URL is likely wrong (dashboard URL or typo) or project is paused."
echo "- If REST (service) fails but Auth is OK: SERVICE_ROLE_KEY wrong/rotated."
echo "- If login fails: anon key wrong or TEST_EMAIL/TEST_PASSWORD mismatch."
echo "- If functions ping fails: function not deployed or wrong headers/apikey."
