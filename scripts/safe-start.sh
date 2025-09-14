#!/usr/bin/env bash
set -Eeuo pipefail
[ -f .env ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true

echo "Running precheck..."
node scripts/precheck.mjs || exit 1

# Ensure alias plugin exists
if ! node -e "try{require('babel-plugin-module-resolver');process.exit(0)}catch(e){process.exit(1)}"; then
  npm i -D babel-plugin-module-resolver
fi

# Kill stale ports / clear caches
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

# Install (idempotent)
npm install

# Start Expo (QR in terminal)
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
