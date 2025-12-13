#!/usr/bin/env bash
set -euo pipefail
set -a; source supa_test.env; set +a
mask(){ v="$1"; [ -z "$v" ]&&echo "(empty)"||{ l=${#v}; [ $l -le 8 ]&&echo "****"||echo "${v:0:4}****${v: -4}";}; }
echo "SUPABASE_URL              = ${SUPABASE_URL:-"(unset)"}"
echo "SUPABASE_ANON_KEY         = $(mask "${SUPABASE_ANON_KEY:-}")"
echo "SUPABASE_SERVICE_ROLE_KEY = $(mask "${SUPABASE_SERVICE_ROLE_KEY:-}")"
echo "TEST_EMAIL                = ${TEST_EMAIL:-"(unset)"}"
echo "TEST_PASSWORD             = $(mask "${TEST_PASSWORD:-}")"
