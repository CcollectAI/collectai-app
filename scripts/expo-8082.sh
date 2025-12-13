#!/usr/bin/env bash
set -e

echo "[1] Kill running Expo/Metro..."
pkill -f "expo" || true
pkill -f "metro" || true
pkill -f "react-native" || true

echo "[2] Clear caches (.expo, Metro)..."
rm -rf .expo || true
rm -rf node_modules/.cache || true

echo "[3] Quick TypeScript check (non-fatal)..."
npx tsc --noEmit || true

echo "[4] Start Expo on port 8082 with DEBUG + clear..."
EXPO_DEBUG=1 npx expo start --clear --port 8082 --localhost
