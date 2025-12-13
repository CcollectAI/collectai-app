#!/usr/bin/env bash
set -euo pipefail

echo "→ Stop Expo/Metro"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro"     2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Free minimal space (safe deletes)"
rm -rf .expo 2>/dev/null || true
rm -rf ~/.npm ~/.cache/npm ~/.cache/expo ~/.expo /tmp/npmcache /tmp/metro-* 2>/dev/null || true

echo "==== Disk status ===="; df -h

echo "→ Use RAM for npm cache"
mkdir -p /dev/shm/npmcache
export NPM_CONFIG_CACHE=/dev/shm/npmcache

# If lock is out of sync, bring it up-to-date without installing
echo "→ Sync lockfile (no install)"
npm install --package-lock-only --no-audit --no-fund || true

echo "→ Try clean install from lock (omit optional deps)"
if npm ci --omit=optional --no-audit --no-fund; then
  echo "✓ npm ci succeeded"
else
  echo "⚠️ npm ci failed — falling back to npm install (will update lock)"
  if npm install --omit=optional --no-audit --no-fund; then
    echo "✓ npm install succeeded"
  else
    echo "⚠️ npm install failed — last resort: rebuild lockfile"
    mv -f package-lock.json package-lock.backup.json 2>/dev/null || true
    npm install --omit=optional --no-audit --no-fund
  fi
fi

echo "→ Ensure expo-router is resolvable"
node -e "require.resolve('expo-router/package.json')" 2>/dev/null || npm i expo-router --no-audit --no-fund --omit=optional

echo "→ Start Expo (tunnel + clear)"
export NPM_CONFIG_CACHE=/dev/shm/npmcache
npx expo start --tunnel --clear
