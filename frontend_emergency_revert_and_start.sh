#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== [1/4] Restoring app/index.tsx from original backup (if available) ==="
INDEX_FILE="app/index.tsx"
CALDEMOBACK="app/index.tsx.bak_calendar_demo"

if [ -f "$CALDEMOBACK" ]; then
  cp "$CALDEMOBACK" "$INDEX_FILE"
  echo "  Restored app/index.tsx from:"
  echo "    $CALDEMOBACK"
else
  echo "  WARNING: $CALDEMOBACK not found."
  echo "  Keeping current app/index.tsx (no restore done)."
fi

echo
echo "=== [2/4] Quick check: key frontend files exist ==="
ls -1 app/index.tsx app/'(tabs)'/_layout.tsx app/'(tabs)'/portfolio.tsx app/'(tabs)'/items.tsx || true
echo

echo "=== [3/4] Cleaning Expo/Metro caches (safe) ==="
rm -rf .expo || true
rm -rf node_modules/.cache || true

if command -v watchman >/dev/null 2>&1; then
  echo "  Clearing watchman watches..."
  watchman watch-del-all || true
fi
echo "  Cache clean step done."

echo
echo "=== [4/4] Starting Expo dev server in TUNNEL mode ==="
echo "  If there is a bundling error, it will be printed below."
echo "  Use the Tunnel URL in Expo Go (enter URL manually)."
echo

EXPO_NO_TYPESCRIPT_CHECK=1 npx expo start --tunnel --clear
