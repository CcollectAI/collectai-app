#!/usr/bin/env bash
set -euo pipefail

echo "== 0) Checkpoint =="
STAMP=$(date +%Y%m%d-%H%M%S)
git add -A || true
git commit -m "checkpoint before schema-utils repair $STAMP" || true

echo "== 1) Node 20 =="
. ~/.nvm/nvm.sh 2>/dev/null || true
nvm use 20 >/dev/null 2>&1 || true

echo "== 2) Clean installs =="
rm -rf node_modules package-lock.json
npm cache clean --force >/dev/null 2>&1 || true
npm install

echo "== 3) Ensure expo-router + metro runtime =="
npm i expo-router@^3 @expo/metro-runtime@^3

echo "== 4) Install @expo/schema-utils with fallbacks =="
(
  set +e
  npm i -D @expo/schema-utils@latest \
  || npm i -D @expo/schema-utils@0.8.2 \
  || npm i -D @expo/schema-utils@0.6.0 \
  || npm i -D @expo/schema-utils@0.5.1
)
# Run postinstall to create build/dist shim if needed
npm run -s postinstall || true

MISSING_BUILD="node_modules/@expo/schema-utils/build/index.js"
DIST_INDEX="node_modules/@expo/schema-utils/dist/index.js"
if [ ! -f "$MISSING_BUILD" ]; then
  if [ -f "$DIST_INDEX" ]; then
    echo "== 5) Creating build → dist shim =="
    mkdir -p "$(dirname "$MISSING_BUILD")"
    echo "module.exports = require('../dist');" > "$MISSING_BUILD"
  else
    echo "❌ Could not find dist/index.js either. Installation failed."
    exit 1
  fi
fi
echo "✅ Verified: @expo/schema-utils provides build/index.js (direct or shim)."

echo "== 6) Save =="
git add -A || true
git commit -m "deps: ensure @expo/schema-utils present + build shim" || true

echo "== 7) Start Expo fresh (tunnel + QR) =="
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
