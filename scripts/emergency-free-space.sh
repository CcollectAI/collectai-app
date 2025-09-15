#!/usr/bin/env bash
set -euo pipefail

echo "==== Disk BEFORE ===="
df -h || true
echo

echo "→ Stop Expo/Metro if running (without killing this shell)"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro"     2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Biggest folders in repo (top 10)"
du -xh --max-depth=1 . | sort -h | tail -n 10 || true
echo

echo "→ Remove heaviest dev folders (safe to delete)"
rm -rf node_modules .expo .turbo .next dist build coverage .cache 2>/dev/null || true
rm -rf android/.gradle android/build 2>/dev/null || true
rm -rf ios/Pods ios/build 2>/dev/null || true

echo "→ Clear user-level caches"
rm -rf ~/.npm ~/.cache/npm /tmp/npmcache ~/.cache/expo ~/.expo ~/.yarn ~/.cache/yarn ~/.pnpm-store 2>/dev/null || true

echo "→ System-level cleanups (won't touch your code)"
sudo journalctl --vacuum-time=3d   2>/dev/null || true
sudo apt-get clean                 2>/dev/null || true
sudo rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* 2>/dev/null || true

if command -v docker >/dev/null 2>&1; then
  echo "→ Optional: prune Docker (can free GBs)"
  docker system prune -af --volumes 2>/dev/null || true
fi

echo "→ Compact git objects (keeps history)"
git rev-parse --git-dir >/dev/null 2>&1 && git gc --prune=now --aggressive >/dev/null || true

echo
echo "==== Disk AFTER CLEAN ===="
df -h || true
echo

echo "→ Reinstall deps fresh (minimal noise)"
npm i --no-audit --no-fund

echo "→ Align icon/runtime packages with Expo SDK"
npx expo install @expo/metro-runtime@~5.0.4 @expo/vector-icons@^14.1.0 react-native@0.79.5 expo-font

echo "→ Dedupe"
npm dedupe || true

echo "→ Start Expo with a clean Metro cache"
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
