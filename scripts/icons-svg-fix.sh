#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "== Disk quick check =="
df -h || true

echo "== Minimal cleanup to free space =="
rm -rf .expo /tmp/metro-* ~/.cache/expo ~/.expo 2>/dev/null || true

echo "== Install SVG-based icons (no fonts needed) =="
# react-native-svg is often already in Expo; this ensures it's present
npx expo install react-native-svg lucide-react-native

echo "== Create Icon shim (maps your Ionicon names to Lucide SVGs) =="
mkdir -p src/components
cat > src/components/Icon.tsx <<'TSX'
import React from 'react';
import {
  LineChart,    // stats-chart-outline
  Images,       // albums-outline
  PlusCircle,   // add-circle-outline
  ShoppingCart, // cart-outline
  Settings,     // settings-outline
  Share2,       // share-outline
  ChevronDown,  // chevron-down
  X,            // close
  Check,        // checkmark
  Image as ImageIcon, // image-outline
  Search,       // search-outline
  Shield        // shield-outline
} from 'lucide-react-native';

type Props = {
  name:
    | 'stats-chart-outline' | 'albums-outline' | 'add-circle-outline' | 'cart-outline'
    | 'settings-outline' | 'share-outline' | 'chevron-down' | 'close'
    | 'checkmark' | 'image-outline' | 'search-outline' | 'shield-outline';
  size?: number;
  color?: string;
};

export default function Icon({ name, size = 20, color = '#0B3D91' }: Props) {
  const p = { size, color };
  switch (name) {
    case 'stats-chart-outline': return <LineChart {...p} />;
    case 'albums-outline':      return <Images {...p} />;
    case 'add-circle-outline':  return <PlusCircle {...p} />;
    case 'cart-outline':        return <ShoppingCart {...p} />;
    case 'settings-outline':    return <Settings {...p} />;
    case 'share-outline':       return <Share2 {...p} />;
    case 'chevron-down':        return <ChevronDown {...p} />;
    case 'close':               return <X {...p} />;
    case 'checkmark':           return <Check {...p} />;
    case 'image-outline':       return <ImageIcon {...p} />;
    case 'search-outline':      return <Search {...p} />;
    case 'shield-outline':      return <Shield {...p} />;
    default: return null;
  }
}
TSX

echo "== Use Icon shim in Tabs (replaces font icons) =="
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak.$ts"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import Icon from '@/components/Icon';
import { Pressable, Share, Text, View } from 'react-native';
import { theme } from '@/theme';

function SettingsButton() {
  return (
    <Link href="/_shelf/settings" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <Icon name="settings-outline" />
      </Pressable>
    </Link>
  );
}
function ShareButton() {
  const onShare = async () => { try { await Share.share({ message: 'Shared from Collect AI' }); } catch {} };
  return (
    <Pressable onPress={onShare} style={{ paddingHorizontal: 12 }}>
      <Icon name="share-outline" />
    </Pressable>
  );
}
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
          tabBarIcon: () => <Icon name="stats-chart-outline" />,
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
          tabBarIcon: () => <Icon name="albums-outline" />,
          headerRight: () => <ShareButton />,
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: () => <Icon name="add-circle-outline" />,
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: 'Marketplace',
          tabBarIcon: () => <Icon name="cart-outline" />,
        }}
      />
    </Tabs>
  );
}
TSX

echo "== Icon test screen using SVG shim =="
mkdir -p app/_shelf
cat > "app/_shelf/icon-test.tsx" <<'TSX'
import { View, Text, ScrollView } from 'react-native';
import Icon from '@/components/Icon';

export default function IconTest() {
  const names: Parameters<typeof Icon>[0]['name'][] = [
    'settings-outline','share-outline','stats-chart-outline','albums-outline',
    'add-circle-outline','cart-outline','chevron-down','close','checkmark',
    'image-outline','search-outline','shield-outline'
  ];
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Text style={{ fontWeight: '800', fontSize: 18 }}>SVG Icons Sanity Check</Text>
      <Text style={{ color: '#64748B' }}>No fonts involved. If you see icons below, we’re good.</Text>
      {names.map(n => (
        <View key={n} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Icon name={n} />
          <Text>{n}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
TSX

echo "== Quick backup (commit + tag + tarball) =="
git add -A || true
git commit -m "[backup $ts] switch to SVG icons" || true
git tag -f "backup-$ts" || true
mkdir -p backups
tar -czf backups/collectai-backup-$ts.tar.gz . \
  --exclude='./backups/*.tar.gz' \
  --exclude='./node_modules' \
  --exclude='./.expo' \
  --exclude='./.git' || true
echo "✔ Backup TAR at backups/collectai-backup-$ts.tar.gz"

echo "== Clean Metro caches =="
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

echo "✅ Done. Next: npx expo start --tunnel --clear  (then tap 'Icon Test')"
