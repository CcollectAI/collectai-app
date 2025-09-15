set -euo pipefail

# Node
[ -f "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"
( command -v nvm >/dev/null 2>&1 && nvm use 20 ) || true

# Make sure expo-router is present and app.json has its plugin
if [ -f app.config.ts ] || [ -f app.config.js ]; then
  echo "Using app.config.* — ensure plugins: ['expo-router'] is set there."
else
  if [ ! -f app.json ] || ! grep -q '"expo-router"' app.json; then
    cp app.json app.json.bak.$(date +%s) 2>/dev/null || true
    cat > app.json <<'JSON'
{
  "expo": {
    "name": "collectorsapp",
    "slug": "collectorsapp",
    "scheme": "collectorsapp",
    "plugins": ["expo-router"],
    "experiments": { "typedRoutes": true }
  }
}
JSON
  fi
fi

# Install deps (creates package-lock.json if missing)
npm install

# Kill stale Metro ports & clear caches
for p in 19000 19001 8081; do
  (command -v fuser >/dev/null && fuser -k "${p}/tcp") >/dev/null 2>&1 || true
  (command -v lsof  >/dev/null && lsof -ti tcp:"$p" | xargs -r kill -9) >/dev/null 2>&1 || true
done
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

# Start dev server (shows QR)
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
