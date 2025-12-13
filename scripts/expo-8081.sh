#!/usr/bin/env bash
set -e

echo "[1] Clear caches..."
rm -rf .expo || true
rm -rf node_modules/.cache || true

echo "[2] Quick TypeScript check (non-fatal)..."
npx tsc --noEmit || true

echo "[3] Start Expo on port 8081..."
EXPO_DEBUG=1 npx expo start --clear --port 8081 --localhost
