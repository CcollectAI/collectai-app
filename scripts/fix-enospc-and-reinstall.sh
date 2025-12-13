#!/usr/bin/env bash
set -euo pipefail

echo "→ Kill Expo/Metro & free ports"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro"     2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Hard clean caches and heavy dirs"
rm -rf node_modules .expo .next .turbo dist build coverage .cache 2>/dev/null || true
rm -rf android/.gradle android/build ios/Pods ios/build 2>/dev/null || true
rm -rf ~/.npm ~/.cache/npm ~/.cache/expo ~/.expo ~/.yarn ~/.cache/yarn ~/.pnpm-store /tmp/npmcache /tmp/metro-* 2>/dev/null || true
sudo journalctl --vacuum-time=2d 2>/dev/null || true
sudo apt-get clean 2>/dev/null || true
sudo rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* 2>/dev/null || true

echo "==== Disk status (before install) ===="
df -h

# Require ~1.2 GB free to install safely
avail_mb="$(df -Pm / | awk 'NR==2{print $4}')"
if [ "${avail_mb:-0}" -lt 1200 ]; then
  echo "❌ Not enough free space (${avail_mb} MB). Need at least ~1200 MB."
  echo "Top space hogs in project:"
  du -xh --max-depth=1 . | sort -h | tail -n 20 || true
  echo "Delete any large archives/backups, then rerun this script."
  exit 2
fi

echo "→ Use RAM-backed npm cache (keeps disk writes tiny)"
mkdir -p /dev/shm/npmcache
export NPM_CONFIG_CACHE=/dev/shm/npmcache

echo "→ Reinstall dependencies"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund --no-optional
else
  npm install --no-audit --no-fund --no-optional
fi

echo "→ Ensure expo-router is resolvable (for config plugin)"
node -e "require.resolve('expo-router/package.json')" 2>/dev/null || {
  echo "expo-router missing, installing minimal…"
  npm install expo-router --no-audit --no-fund --no-optional
}

echo "→ Ensure app.json includes the expo-router plugin (idempotent)"
python3 - <<'PY'
import json, os, sys
p = 'app.json'
if not os.path.exists(p):
    sys.exit(0)
data = json.load(open(p))
app = data.get('expo') or data
plugins = app.get('plugins') or []
if 'expo-router' not in plugins:
    plugins.append('expo-router')
    app['plugins'] = plugins
    data['expo'] = app
    json.dump(data, open(p,'w'), indent=2)
    print("app.json updated: added expo-router plugin")
else:
    print("app.json: expo-router plugin already present")
PY

echo "→ Final disk check"
df -h

echo "→ Start Expo (with tunnel, clear caches)"
export NPM_CONFIG_CACHE=/dev/shm/npmcache
npx expo start --tunnel --clear
