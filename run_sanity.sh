#!/usr/bin/env bash
set -euo pipefail

# Load env (required by all scripts)
if [[ -f ./supa_test.env ]]; then
  set -a; . ./supa_test.env; set +a
else
  echo "❌ Missing ./supa_test.env — create it first."; exit 1
fi

# Quick guardrails
: "${SUPA_REF:?SUPA_REF missing in supa_test.env}"
: "${ANON_KEY:?ANON_KEY missing in supa_test.env}"
: "${TEST_EMAIL:?TEST_EMAIL missing in supa_test.env}"
: "${TEST_PASSWORD:?TEST_PASSWORD missing in supa_test.env}"

mkdir -p logs

# Helper: (re)login if JWT missing/expired
ensure_jwt () {
  local ok=0
  if [[ -f ./.jwt ]]; then
    echo "→ Checking existing JWT…"
    if ./check_jwt.sh; then ok=1; else ok=0; fi
  fi
  if [[ $ok -eq 0 ]]; then
    echo "→ Getting a fresh JWT…"
    rm -f ./.jwt || true
    ./login_and_get_jwt.sh
    ./check_jwt.sh
  fi
}

ensure_jwt

echo "=== Running strict E2E ==="
./sanity_e2e_strict.sh 2>&1 | tee -a "logs/sanity_$(date +%F_%H%M%S).log"
