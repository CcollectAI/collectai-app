#!/usr/bin/env bash
set -euo pipefail
URL="${1:-http://127.0.0.1:8080/health}"
code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$URL" || true)
[ "$code" = "200" ] || exit 1
