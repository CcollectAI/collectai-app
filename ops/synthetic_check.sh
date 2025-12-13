#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8081}"
fail=0
for path in /healthz /ops/status ; do
  if ! curl -fsS "http://127.0.0.1:${PORT}${path}" >/dev/null; then
    echo "FAIL ${path}"
    fail=1
  fi
done
exit $fail
