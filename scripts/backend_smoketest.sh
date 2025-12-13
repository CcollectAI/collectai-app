#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"
API_KEY_HEADER="${API_KEY_HEADER:-X-API-Key}"
API_KEY_VALUE="${API_KEY_VALUE:-}"

echo "=== Backend smoketest ==="
echo "BASE_URL      = $BASE_URL"
echo "API_KEY_HEADER= $API_KEY_HEADER"
echo "API_KEY_VALUE = ${API_KEY_VALUE:+(set)}"
echo

curl_cmd=(
  curl -sS -o /dev/null -w "%{http_code}"
)

auth_args=()
if [ -n "$API_KEY_VALUE" ]; then
  auth_args=(-H "$API_KEY_HEADER: $API_KEY_VALUE")
fi

check() {
  local path="$1"
  local label="$2"

  local url="${BASE_URL}${path}"
  local code

  code="$("${curl_cmd[@]}" "${auth_args[@]}" "$url" || echo "000")"

  if [ "$code" = "200" ]; then
    echo "[OK]   $label ($path) -> $code"
  else
    echo "[FAIL] $label ($path) -> $code"
  fi
}

check "/portfolio/overview"  "portfolio overview"
check "/portfolio/items"     "portfolio items"
check "/portfolio/timeseries?range=30d" "portfolio timeseries"
check "/marketplace/listings" "marketplace listings"
check "/eval/summary"        "eval summary"

echo
echo "=== Done. Use API_KEY_VALUE env + BASE_URL arg to tweak. ==="

