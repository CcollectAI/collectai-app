#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Cleaning Metro cache and node_modules cache (non-destructive)..."

# Metro cache
rm -rf .expo/.cache || true
rm -rf .expo/web/cache || true

# Optional: clear watchman if installed
if command -v watchman >/dev/null 2>&1; then
  watchman watch-del-all || true
fi

echo "Starting Expo with cache clear and TS checking reduced..."
EXPO_NO_TYPESCRIPT_CHECK=1 npx expo start --clear
