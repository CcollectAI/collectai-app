#!/usr/bin/env bash
set -euo pipefail

echo "==== Disk status (before) ===="
df -h || true
echo

echo "→ Stop dev servers & free ports"
pkill -f "expo"    2>/dev/null || true
pkill -f "metro"   2>/dev/null || true
pkill -f "node"    2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Clear project & tool caches (safe)"
rm -rf .expo /tmp/metro-* ~/.cache/expo ~/.expo 2>/dev/null || true
rm -rf /tmp/npmcache ~/.npm ~/.cache/npm 2>/dev/null || true
rm -rf ~/.yarn ~/.cache/yarn 2>/dev/null || true
command -v watchman >/dev/null && watchman watch-del-all || true
rm -rf /usr/local/var/run/watchman/$USER-state 2>/dev/null || true

echo "→ Optional heavy cleanups"
# Android/Gradle caches (if any; Expo managed apps don't need them during web/QR dev)
rm -rf ~/.gradle/caches ~/.android/build-cache 2>/dev/null || true

# System logs & apt cache (needs sudo; harmless)
sudo journalctl --vacuum-time=3d     2>/dev/null || true
sudo rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* 2>/dev/null || true
sudo apt-get clean                   2>/dev/null || true

echo "→ Compact git objects (keeps code intact)"
git rev-parse --git-dir >/dev/null 2>&1 && git gc --prune=now --aggressive || true

echo "→ Remove node_modules to reclaim space (will re-install)"
rm -rf node_modules 2>/dev/null || true

echo "==== Disk status (after cleanup) ===="
df -h || true
echo

echo "→ Reinstall minimal deps without extra noise"
npm i --no-audit --no-fund

echo "→ Align icon + runtime packages to what Expo expects"
npx expo install @expo/metro-runtime@~5.0.4 @expo/vector-icons@^14.1.0 react-native@0.79.5 expo-font

echo "→ Dedupe any duplicate packages"
npm dedupe || true

echo "→ Start Expo with a clean Metro cache"
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
