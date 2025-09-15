set -euo pipefail

echo "== 0) Node & quick autosave =="
if [ -f "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi
( command -v nvm >/dev/null 2>&1 && nvm use 20 ) || true
git add -A || true
git commit -m "autosave before expo-router fix $(date +%Y%m%d-%H%M%S)" || true
git tag -f autosave-latest || true

echo "== 1) Ensure app.json has the expo-router plugin =="
if [ -f app.config.ts ] || [ -f app.config.js ]; then
  echo "You have app.config.* — leaving it as-is (make sure plugins: ['expo-router'] is declared there)."
else
  if [ -f app.json ]; then cp app.json app.json.bak.$(date +%s); fi
  # Create or patch app.json with the plugin + experiments block
  cat > app.json <<'JSON'
{
  "expo": {
    "name": "collectorsapp",
    "slug": "collectorsapp",
    "scheme": "collectorsapp",
    "plugins": ["expo-router"],
    "experiments": {
      "typedRoutes": true
    }
  }
}
JSON
fi

echo "== 2) Ensure minimal layouts exist (expo-router only) =="
mkdir -p app "(tabs)" >/dev/null 2>&1 || true
mkdir -p app/(tabs)

# Root layout (no NavigationContainer here)
cat > app/_layout.tsx <<'TSX'
import React from "react";
import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </SafeAreaProvider>
  );
}
TSX

# Tabs layout stub (header hidden; icons come from Ionicons in your screens)
cat > app/(tabs)/_layout.tsx <<'TSX'
import React from "react";
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return <Tabs screenOptions={{ headerShown: false }} />;
}
TSX

# A trivial NotFound page to satisfy the router
cat > app/+not-found.tsx <<'TSX'
import React from "react";
import { View, Text } from "react-native";
export default function NotFound() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <Text>Not Found</Text>
    </View>
  );
}
TSX

echo "== 3) Install the correct expo-router for your SDK =="
# This uses Expo's compatibility resolver (no version guessing)
npx -y expo install expo-router

echo "== 4) Clean caches that commonly poison plugin resolution =="
# Kill ports if they are stuck
for p in 19000 19001 8081; do
  (command -v fuser >/dev/null && fuser -k "${p}/tcp") >/dev/null 2>&1 || true
  (command -v lsof  >/dev/null && lsof -ti tcp:"$p" | xargs -r kill -9) >/dev/null 2>&1 || true
done
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

echo "== 5) Ensure node_modules are present =="
# If there's no lockfile yet, do a fresh install
if [ ! -f package-lock.json ]; then
  npm install
else
  # Quick health check: try requiring expo-router plugin file path by installing if needed
  [ -d node_modules ] || npm ci || npm install
fi

echo "== 6) Start Expo with tunnel + QR =="
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
