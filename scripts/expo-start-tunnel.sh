#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf .expo/.cache || true
rm -rf .expo/web/cache || true

if command -v watchman >/dev/null 2>&1; then
  watchman watch-del-all || true
fi

EXPO_NO_TYPESCRIPT_CHECK=1 npx expo start --tunnel --clear
