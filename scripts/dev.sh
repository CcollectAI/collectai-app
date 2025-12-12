#!/usr/bin/env bash
set -euo pipefail
pkill -f "expo start" 2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true
# Optional: clear caches
rm -rf .expo /tmp/metro-* ~/.cache/expo ~/.expo 2>/dev/null || true
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
