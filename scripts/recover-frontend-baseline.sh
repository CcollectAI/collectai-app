#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
ts="$(date +%Y%m%d_%H%M%S)"

echo "== BACKUP (non-destructive) =="
mkdir -p backups/runtime_baseline
tar -czf "backups/runtime_baseline/recover_baseline_${ts}.tgz" \
  package.json package-lock.json app.json tsconfig.json app src scripts 2>/dev/null || true
echo "Backup written: backups/runtime_baseline/recover_baseline_${ts}.tgz"

echo
echo "== CHECK NODE VERSION =="
node -v || true
echo "If you see v22.x here, we will switch to Node 20 LTS using nvm."

echo
echo "== ENSURE NVM + NODE 20 LTS =="
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "nvm not found. Installing nvm..."
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck disable=SC1090
source "$NVM_DIR/nvm.sh"

nvm install 20
nvm use 20
node -v
npm -v

echo
echo "== CLEAN INSTALL (safe) =="
rm -rf node_modules
rm -f package-lock.json.bak_recover || true
cp package-lock.json "package-lock.json.bak_recover_${ts}" 2>/dev/null || true

# Keep package-lock.json, but we will let Expo align deps afterward
npm ci || npm install

echo
echo "== ALIGN EXPO PACKAGES TO EXPECTED VERSIONS =="
# This uses expo's version resolution for the installed Expo SDK.
npx expo install --check

echo
echo "== CLEAR EXPO/METRO CACHES =="
rm -rf .expo .expo-shared .cache node_modules/.cache 2>/dev/null || true

echo
echo "== START EXPO (CI=1 makes output deterministic; no --non-interactive) =="
echo "If it still 'doesn't load', we need DEVICE RUNTIME LOGS next (see instructions after this finishes)."
CI=1 npx expo start -c
