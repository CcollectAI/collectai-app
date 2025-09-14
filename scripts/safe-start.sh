#!/usr/bin/env bash
set -euo pipefail

echo "Node: $(node -v)"
echo "Running precheck (non-blocking)..."
npm run precheck || true

# Kill stale metro ports & clear caches
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

# Load env if present
[ -f .env ] && export $(grep -v '^#' .env | xargs) || true

# Start Expo (tunnel prints QR in this terminal)
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
