set -euo pipefail

echo "== 0) Node & quick autosave =="
if [ -f "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi
( command -v nvm >/dev/null 2>&1 && nvm use 20 ) || true
git add -A || true
git commit -m "autosave before expo-router fix $(date +%Y%m%d-%H%M%S)" || true
git tag -f autosave-latest || true

echo "== 1) Ensure app.json has the expo-router plugin =="
if [ -f app.config.ts ] || [ -f app.config.js ]; then
  echo "Detected app.config.* — please ensure it contains:  plugins: ['expo-router']"
  echo "Proceeding without modifying app.config.*"
else
  if [ -f app.json ]; then cp app.json app.json.bak.$(date +%s); fi
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

echo "== 2) Ensure minimal layouts exist (expo-router only) =="
mkdir -p "app/(tabs)" app src

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

# Tabs layout stub (header hidden)
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return <Tabs screenOptions={{ headerShown: false }} />;
}
TSX

# NotFound page
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

echo "== 3) Install the correct expo-router for this SDK =="
npx -y expo install expo-router

echo "== 4) Clean caches (Metro/Expo) and kill stale ports =="
for p in 19000 19001 8081; do
  (command -v fuser >/dev/null && fuser -k "${p}/tcp") >/dev/null 2>&1 || true
  (command -v lsof  >/dev/null && lsof -ti tcp:"$p" | xargs -r kill -9) >/dev/null 2>&1 || true
done
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

echo "== 5) Ensure node_modules exist =="
if [ ! -f package-lock.json ]; then
  npm install
else
  [ -d node_modules ] || npm install
fi

echo "== 6) Start Expo with tunnel + QR =="
EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear
