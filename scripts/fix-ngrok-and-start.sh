#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/collectors-merge-recovered}"
cd "$PROJECT_DIR" || { echo "❌ Project not found: $PROJECT_DIR"; exit 1; }

echo "→ Stop Expo/Metro (safe)"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro" 2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

# Prefer a local devDependency to avoid global perms issues
echo "→ Checking local @expo/ngrok"
if node -e "require.resolve('@expo/ngrok/package.json')" 2>/dev/null; then
  echo "✓ @expo/ngrok is already installed locally."
else
  echo "→ Installing @expo/ngrok locally (devDependency)…"
  if ! npm install -D @expo/ngrok@^4.1.0 --no-audit --no-fund; then
    echo "⚠️ Local install failed; trying user-global prefix at ~/.npm-global"
    mkdir -p "$HOME/.npm-global"
    npm config set prefix "$HOME/.npm-global"
    export PATH="$HOME/.npm-global/bin:$PATH"
    if ! grep -q 'npm-global/bin' "$HOME/.bashrc" 2>/dev/null; then
      echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
      echo "→ Appended PATH update to ~/.bashrc"
    fi
    npm install -g @expo/ngrok@^4.1.0 --no-audit --no-fund
    echo "✓ Installed @expo/ngrok globally under ~/.npm-global"
  else
    echo "✓ Installed @expo/ngrok locally"
  fi
fi

echo "→ Starting Expo with tunnel (clean cache)"
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
