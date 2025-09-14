#!/usr/bin/env bash
set -Eeuo pipefail
. ~/.nvm/nvm.sh 2>/dev/null || true
nvm use 20 >/dev/null 2>&1 || nvm install 20 >/dev/null 2>&1 || true

echo "Running precheck..."
npm run precheck || exit 1

sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
