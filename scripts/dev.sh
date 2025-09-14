#!/usr/bin/env bash
set -euo pipefail

# Load NVM if present, prefer Node 20
if [ -n "${NVM_DIR:-}" ] && [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
  nvm use 20 >/dev/null 2>&1 || true
fi

# Load .env (harmless if missing)
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs) || true
fi

# Run precheck (fast fail if something’s broken)
if npm run precheck >/dev/null 2>&1; then
  echo "Precheck OK."
else
  echo "Precheck failed — showing output:"
  npm run precheck || true
  echo "Fix precheck issues, then re-run: npm run dev"
  exit 1
fi

# Free any stale dev ports (no sudo prompt)
for p in 19000 19001 8081; do
  (command -v fuser >/dev/null && fuser -k "${p}/tcp") >/dev/null 2>&1 || true
  (command -v lsof  >/dev/null && lsof -ti tcp:"$p" | xargs -r kill -9) >/dev/null 2>&1 || true
done

# Clear Metro/Expo caches
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

# Start Expo with tunnel so QR works anywhere
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
