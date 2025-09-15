#!/usr/bin/env bash
set -euo pipefail

echo "→ Install/ensure icon + font deps"
npx expo install @expo/vector-icons expo-font >/dev/null

echo "→ Normalize theme (colors, spacing, type)"
mkdir -p src
[ -f src/theme.ts ] && cp src/theme.ts src/theme.ts.bak
cat > src/theme.ts <<'TS'
export const theme = {
  colors: {
    brand: { base: "#1ABC9C" },   // Tiffany-ish accent
    navy: "#0B3D91",
    bg: "#E6F7F8",                // page background
    card: "#FFFFFF",              // card background (text/numbers sit on white)
    text: "#0B3D91",
    subtext: "#64748B",
    up: "#10B981",
    down: "#EF4444",
    border: "#E5E7EB",
  },
  spacing: { xxs: 2, xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  text: {
    title: { size: 16, weight: '800' as const },
    h1:    { size: 30, weight: '800' as const },
    h2:    { size: 20, weight: '800' as const },
    body:  { size: 14, weight: '500' as const },
    small: { size: 12, weight: '500' as const },
  },
};
TS

echo "→ Ensure Card uses consistent padding & square corners"
mkdir -p src/components
[ -f src/components/Card.tsx ] && cp src/components/Card.tsx src/components/Card.tsx.bak
cat > src/components/Card.tsx <<'TSX'
import { View, ViewProps } from 'react-native';
import { theme } from '@/theme';

export default function Card({ style, ...props }: ViewProps) {
  return (
    <View
      style={[{
        backgroundColor: theme.colors.card,
        padding: theme.spacing.lg,
        borderColor: theme.colors.border,
        borderWidth: 1,
      }, style]}
      {...props}
    />
  );
}
TSX

echo "→ Load Ionicons font at app start (fixes 'icons not loading')"
[ -f app/_layout.tsx ] && cp app/_layout.tsx app/_layout.tsx.bak
cat > app/_layout.tsx <<'TSX'
import { Stack } from 'expo-router';
import { useEffect } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  // Explicitly load Ionicons so tab/header icons render on all platforms
  const [fontsLoaded] = useFonts(Ionicons.font);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(()=>{});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTintColor: theme.colors.navy,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="_shelf/settings" options={{ title: 'Settings' }} />
    </Stack>
  );
}
TSX

echo "→ Tabs: consistent header + icons wired"
mkdir -p "app/(tabs)"
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';
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

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '800' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Collect AI',
          tabBarLabel: 'Collect AI',
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart-outline" size={size} color={color} />,
          headerRight: () => <SettingsButton />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarIcon: ({ color, size }) => <Ionicons name="albums-outline" size={size} color={color} />,
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

echo "→ Unify page paddings/gaps across major tabs"
# Portfolio
if [ -f "app/(tabs)/index.tsx" ]; then
  sed -i.bak 's/contentContainerStyle={{[^}]*}}/contentContainerStyle={{ padding: 16, gap: 16 }}/' "app/(tabs)/index.tsx" || true
fi
# Items
if [ -f "app/(tabs)/items.tsx" ]; then
  sed -i.bak 's/contentContainerStyle={{[^}]*}}/contentContainerStyle={{ padding: 16, gap: 16 }}/' "app/(tabs)/items.tsx" || true
fi
# Add
if [ -f "app/(tabs)/add.tsx" ]; then
  sed -i.bak 's/contentContainerStyle={{[^}]*}}/contentContainerStyle={{ padding: 16, gap: 16 }}/' "app/(tabs)/add.tsx" || true
fi
# Marketplace
if [ -f "app/(tabs)/marketplace.tsx" ]; then
  sed -i.bak 's/contentContainerStyle={{[^}]*}}/contentContainerStyle={{ padding: 16, gap: 16 }}/' "app/(tabs)/marketplace.tsx" || true
fi

echo "→ Done. Icons will render after fonts load; spacing is now consistent."
