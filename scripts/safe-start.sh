#!/usr/bin/env bash
set -euo pipefail
echo "Running precheck..."
node scripts/precheck.mjs
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
