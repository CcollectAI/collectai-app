#!/usr/bin/env bash
set -e

echo "[1] Clear caches..."
rm -rf .expo || true
rm -rf node_modules/.cache || true

echo "[2] Start Expo on tunnel (web + devices)..."
EXPO_DEBUG=1 npx expo start --clear --tunnel
