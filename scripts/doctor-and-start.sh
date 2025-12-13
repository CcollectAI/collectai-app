#!/usr/bin/env bash
set -euo pipefail

echo "→ Kill Expo/Metro & free ports"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro"     2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Tiny cache cleanup (safe)"
rm -rf .expo /tmp/npmcache /tmp/metro-* ~/.npm ~/.cache/npm ~/.cache/expo ~/.expo 2>/dev/null || true

echo "==== Disk ===="; df -h

echo "→ Use RAM for npm cache"
mkdir -p /dev/shm/npmcache
export NPM_CONFIG_CACHE=/dev/shm/npmcache

# If node_modules is missing or incomplete, do a minimal lock resync + install
if [ ! -d node_modules ] || [ ! -f node_modules/expo-router/package.json ]; then
  echo "→ Resync lockfile (no install writes yet)"
  npm install --package-lock-only --no-audit --no-fund || true

  echo "→ Install (omit optional deps to save space)"
  if ! npm ci --omit=optional --no-audit --no-fund; then
    npm install --omit=optional --no-audit --no-fund
  fi
fi

echo "→ Ensure expo-router resolves (config plugin)"
node -e "require.resolve('expo-router/package.json')" 2>/dev/null || npm i expo-router --no-audit --no-fund --omit=optional

echo "→ Sanity check: key files"
for f in "app/(tabs)/_layout.tsx" "app/(tabs)/index.tsx" "app/(tabs)/items.tsx" "app/(tabs)/add.tsx" "app/(tabs)/marketplace.tsx"; do
  [ -f "$f" ] || echo "WARN missing $f"
done

echo "→ Health route (if not present)"
mkdir -p app/_shelf
[ -f app/_shelf/health.tsx ] || cat > app/_shelf/health.tsx <<'TSX'
import { View, Text } from 'react-native';
import { theme } from '@/theme';
export default function Health(){
  return (
    <View style={{flex:1,justifyContent:'center',alignItems:'center',backgroundColor:theme.colors.bg}}>
      <Text style={{backgroundColor:'#fff',padding:10,borderWidth:1,borderColor:theme.colors.border,color:theme.colors.navy,fontWeight:'800'}}>
        ✅ Expo Router up & rendering
      </Text>
    </View>
  );
}
TSX

echo "→ Start Expo (tunnel + clear caches)"
export NPM_CONFIG_CACHE=/dev/shm/npmcache
npx expo start --tunnel --clear
