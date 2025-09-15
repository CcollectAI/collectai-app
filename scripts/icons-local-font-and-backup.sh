#!/usr/bin/env bash
set -euo pipefail

ts="$(date -u +%Y%m%d-%H%M%S)"

echo "== 1) Local Ionicons font: copy TTF into assets =="
mkdir -p assets/fonts
# Try common locations in node_modules and copy the TTF locally so Metro MUST bundle it.
for p in \
  node_modules/@expo/vector-icons/build/vendor/react-native-vector-icons/Fonts/Ionicons.ttf \
  node_modules/react-native-vector-icons/Fonts/Ionicons.ttf \
  node_modules/@expo/vector-icons/build/vendor/react-native-vector-icons/Fonts/ionicons.ttf
do
  if [ -f "$p" ]; then
    cp "$p" assets/fonts/Ionicons.ttf
    echo "✔ Copied $p -> assets/fonts/Ionicons.ttf"
    break
  fi
done
if [ ! -f assets/fonts/Ionicons.ttf ]; then
  echo "❌ Could not find Ionicons.ttf in node_modules. Run: npm i @expo/vector-icons && npx expo install expo-font"
  exit 1
fi

echo "== 2) Font preloader uses the local asset =="
mkdir -p src/lib
cat > src/lib/loadFonts.ts <<'TS'
import * as Font from 'expo-font';

// Load the local Ionicons.ttf we just copied into assets/fonts.
// Using a local require() guarantees Metro includes it in the bundle.
export async function loadVectorFonts() {
  try {
    await Font.loadAsync({
      Ionicons: require('../../assets/fonts/Ionicons.ttf'),
    });
    console.log('[fonts] Ionicons (local) loaded');
  } catch (e) {
    console.warn('[fonts] Ionicons failed to load', e);
  }
}
TS

echo "== 3) Root layout waits for font, then renders =="
[ -f app/_layout.tsx ] && cp app/_layout.tsx app/_layout.tsx.bak.$ts
cat > app/_layout.tsx <<'TSX'
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState } from 'react';
import { theme } from '@/theme';
import { loadVectorFonts } from '@/lib/loadFonts';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      await loadVectorFonts();  // force-load Ionicons from local asset
      setReady(true);
      SplashScreen.hideAsync().catch(()=>{});
    })();
  }, []);

  if (!ready) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card }, // white header
        headerTintColor: theme.colors.navy,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="_shelf/icon-test" options={{ title: 'Icon test' }} />
      <Stack.Screen name="_shelf/settings" options={{ title: 'Settings' }} />
    </Stack>
  );
}
TSX

echo "== 4) Make sure we have an easy way to open Icon Test =="
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak.$ts"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable, Share, Text, View } from 'react-native';
import { theme } from '@/theme';

function SettingsButton() {
  return (
    <Link href="/_shelf/settings" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <Ionicons name="settings-outline" size={20} color={theme.colors.navy} />
      </Pressable>
    </Link>
  );
}
function ShareButton() {
  const onShare = async () => { try { await Share.share({ message: 'Shared from Collect AI' }); } catch {} };
  return (
    <Pressable onPress={onShare} style={{ paddingHorizontal: 12 }}>
      <Ionicons name="share-outline" size={20} color={theme.colors.navy} />
    </Pressable>
  );
}
// DEV-only button to open /_shelf/icon-test
function DevIconTestButton() {
  if (!__DEV__) return null as any;
  return (
    <Link href="/_shelf/icon-test" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800' }}>Icon Test</Text>
      </Pressable>
    </Link>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        headerStyle: { backgroundColor: theme.colors.card },
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '800' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Portfolio',
          tabBarLabel: 'Portfolio',
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart-outline" size={size} color={color} />,
          headerRight: () => (
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <DevIconTestButton />
              <SettingsButton />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarLabel: 'Items',
          tabBarIcon: ({ color, size }) => <Ionicons name="albums-outline" size={size} color={color} />,
          headerRight: () => <ShareButton />,
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: 'Marketplace',
          tabBarIcon: ({ color, size }) => <Ionicons name="cart-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
TSX

echo "== 5) Minimal Icon Test screen shows text even if icons fail =="
mkdir -p app/_shelf
cat > app/_shelf/icon-test.tsx <<'TSX'
import { View, Text, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function IconTest() {
  const names = [
    'settings-outline','share-outline','stats-chart-outline','albums-outline',
    'add-circle-outline','cart-outline','chevron-down','close','checkmark',
    'image-outline','search-outline','shield-outline'
  ];
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Text style={{ fontWeight: '800', fontSize: 18 }}>Ionicons Sanity Check</Text>
      <Text style={{ color: '#64748B' }}>If you don't see icons, you should still see this text.</Text>
      {names.map(n => (
        <View key={n} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Ionicons name={n as any} size={22} color="#0B3D91" />
          <Text>{n}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
TSX

echo "== 6) QUICK BACKUP =="
# Commit everything, tag, and write a tarball under backups/
git add -A || true
git commit -m "[backup $ts] quick backup before icon fix" || true
git tag -f "backup-$ts" || true
mkdir -p backups
tar -czf backups/collectai-backup-$ts.tar.gz . \
  --exclude='./backups/*.tar.gz' \
  --exclude='./node_modules' \
  --exclude='./.expo' \
  --exclude='./.git'
echo "✔ Backup TAR: backups/collectai-backup-$ts.tar.gz"

echo
echo "== NEXT =="
echo "1) If disk is tight, remove node_modules and reinstall:"
echo "   rm -rf node_modules && npm i"
echo "2) Start clean: npx expo start --tunnel --clear"
echo "3) Tap 'Icon Test' on the Portfolio header."
