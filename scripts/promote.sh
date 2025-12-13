#!/usr/bin/env bash
set -euo pipefail
PORT=${PORT:-8081}
AUTH=${AUTH:?set AUTH=your_service_key}
cat="$1"; ver="$2"
curl -s -X POST "http://127.0.0.1:${PORT}/admin/promote/${cat}/${ver}" \
  -H "Authorization: Bearer ${AUTH}" | jq .
