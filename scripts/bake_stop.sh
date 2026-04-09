#!/usr/bin/env bash
# Cleanly stop the bake (uvicorn + workers).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$REPO_ROOT/bake.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "stopping bake pid $PID"
    kill "$PID"
    sleep 2
    kill -9 "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi
pkill -f "uvicorn main:app" 2>/dev/null || true
echo "bake stopped"
