#!/usr/bin/env bash
set -euo pipefail
if [ -x ".venv/bin/python" ]; then exec .venv/bin/python "$@"; fi
if command -v python3 >/dev/null 2>&1; then exec python3 "$@"; fi
if command -v python  >/dev/null 2>&1; then exec python  "$@"; fi
echo "No python runtime found (need python3)"; exit 1
