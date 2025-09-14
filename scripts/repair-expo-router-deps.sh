#!/usr/bin/env bash
set -euo pipefail

echo "== 0) Save a checkpoint =="
STAMP=$(date +%Y%m%d-%H%M%S)
git add -A || true
git commit -m "checkpoint before expo-router dep repair $STAMP" || true

echo "== 1) Use Node 20 =="
. ~/.nvm/nvm.sh 2>/dev/null || true
nvm use 20 >/dev/null 2>&1 || true

echo "== 2) Clear caches & remove node_modules =="
rm -rf node_modules package-lock.json
npm cache clean --force >/dev/null 2>&1 || true

echo "== 3) Reinstall deps =="
npm install

echo "== 4) Ensure expo-router and its runtime (safe to re-install) =="
npm i expo-router@^3 @expo/metro-runtime@^3

echo "== 5) Add the missing plugin dep (@expo/schema-utils) =="
npm i -D @expo/schema-utils@^0.7.0

echo "== 6) Verify the file that was missing =="
if [ ! -f node_modules/@expo/schema-utils/build/index.js ]; then
  echo "❌ Still missing: node_modules/@expo/schema-utils/build/index.js"
  echo "   Something is wrong with npm or the package version. Try:"
  echo "     npm i -D @expo/schema-utils@latest"
  exit 1
fi
echo "✅ Verified: @expo/schema-utils/build/index.js is present."

echo "== 7) Save post-repair checkpoint =="
git add -A || true
git commit -m "deps: fix expo-router plugin by adding @expo/schema-utils and reinstalling" || true

echo "== 8) Start Expo (tunnel + fresh caches) =="
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
