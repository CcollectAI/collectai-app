#!/usr/bin/env bash
set -euo pipefail

echo "→ Align packages to what Expo expects (from your warning)"
npx expo install @expo/metro-runtime@~5.0.4 @expo/vector-icons@^14.1.0 react-native@0.79.5 expo-font >/dev/null

echo "→ Preload Ionicons font before first paint"
[ -f "app/_layout.tsx" ] && cp "app/_layout.tsx" "app/_layout.tsx.bak"
cat > "app/_layout.tsx" <<'TSX'
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import * as Font from 'expo-font';
import { useEffect, useState } from 'react';
import Ionicons from '@expo/vector-icons/Ionicons';
import { theme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    (async () => {
      try { await Font.loadAsync(Ionicons.font); }
      finally { setReady(true); SplashScreen.hideAsync().catch(()=>{}); }
    })();
  }, []);
  if (!ready) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card },
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

echo "→ Tabs: use Ionicons default import + safe glyphs"
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, Share } from 'react-native';
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
          headerRight: () => <SettingsButton />,
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

echo "→ CompactSelect: Ionicons chevron/close/check"
[ -f "src/components/CompactSelect.tsx" ] && cp "src/components/CompactSelect.tsx" "src/components/CompactSelect.tsx.bak"
cat > "src/components/CompactSelect.tsx" <<'TSX'
import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { theme } from '@/theme';

type Props = {
  title?: string;
  value?: string | null;
  options: string[];
  placeholder?: string;
  onChange: (v: string) => void;
  searchable?: boolean;
};

export default function CompactSelect({ title, value, options, placeholder = 'Select…', onChange, searchable = false }: Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const show = () => {
    try {
      // @ts-ignore
      triggerRef.current?.measureInWindow?.((x: number, y: number, w: number, h: number) => {
        setAnch({ x, y, w, h });
        setOpen(true);
      });
    } catch {
      setAnch(null);
      setOpen(true);
    }
  };
  const hide = () => setOpen(false);

  const filtered = query ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase())) : options;

  const { width: SW, height: SH } = Dimensions.get('window');
  const POPOVER_W = 260;
  const left = Math.max(8, Math.min((anch?.x ?? 16), SW - POPOVER_W - 8));
  const topBase = (anch ? anch.y + anch.h + 6 : 120);
  const maxH = Math.max(160, Math.min(320, SH - topBase - 16));
  const top = Math.min(topBase, SH - maxH - 8);

  return (
    <>
      <Pressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }}>
        <View style={{
          backgroundColor: theme.colors.card,
          borderWidth: 1,
          borderColor: theme.colors.border,
          paddingVertical: theme.spacing.xs,
          paddingHorizontal: theme.spacing.sm,
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.spacing.xs,
        }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{value || placeholder}</Text>
          <Ionicons name="chevron-down" size={14} color={theme.colors.subtext} />
        </View>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
        <Pressable onPress={hide} style={{ flex: 1, backgroundColor: 'rgba(11,61,145,0.05)' }}>
          <Pressable
            onPress={() => {}}
            style={{
              position: 'absolute',
              top,
              left,
              width: POPOVER_W,
              backgroundColor: theme.colors.card,
              borderWidth: 1,
              borderColor: theme.colors.border,
              padding: theme.spacing.md,
              maxHeight: maxH,
            }}
          >
            {title ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: theme.spacing.sm }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '800' }}>{title}</Text>
                <Ionicons name="close" size={16} color={theme.colors.subtext} />
              </View>
            ) : null}

            {searchable ? (
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="Search…"
                placeholderTextColor={theme.colors.subtext}
                style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff', marginBottom: theme.spacing.sm }}
              />
            ) : null}

            <ScrollView keyboardShouldPersistTaps="handled">
              {filtered.map((opt, idx) => {
                const selected = value === opt;
                return (
                  <Pressable key={opt} onPress={() => { onChange(opt); hide(); }}>
                    <View style={{
                      paddingVertical: theme.spacing.md,
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderTopWidth: idx === 0 ? 0 : 1,
                      borderColor: theme.colors.border,
                    }}>
                      <Text style={{ color: theme.colors.navy, fontWeight: selected ? '800' : '600' }}>{opt}</Text>
                      {selected ? <Ionicons name="checkmark" size={16} color={theme.colors.navy} /> : null}
                    </View>
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}
TSX

echo "→ SearchRow: Ionicons image placeholder"
[ -f "src/components/SearchRow.tsx" ] && cp "src/components/SearchRow.tsx" "src/components/SearchRow.tsx.bak"
cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { theme } from '@/theme';

export default function SearchRow({ title, subtitle, price, badge, thumbUri }: {
  title: string; subtitle: string; price: string; badge?: string; thumbUri?: string | null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.md }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <Ionicons name="image-outline" size={18} color={theme.colors.subtext} />}
      </View>
      <View style={{ flex: 1, paddingRight: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '600' }} numberOfLines={1}>{title}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }} numberOfLines={1}>{subtitle}</Text>
        {badge ? <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>{badge}</Text> : null}
      </View>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{price}</Text>
    </View>
  );
}
TSX

echo "→ ShieldBadge: Ionicons shield + tier"
[ -f "src/components/ShieldBadge.tsx" ] && cp "src/components/ShieldBadge.tsx" "src/components/ShieldBadge.tsx.bak"
cat > "src/components/ShieldBadge.tsx" <<'TSX'
import { View, Text } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';
const COLORS: Record<Tier, string> = { silver: '#C0C0C0', gold: '#D4AF37', platinum: '#B0BEC5' };

export default function ShieldBadge({ tier }: { tier: Tier }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', borderWidth: 1, borderColor: COLORS[tier], paddingVertical: 2, paddingHorizontal: 6 }}>
      <Ionicons name="shield-outline" size={14} color={theme.colors.navy} />
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12, marginLeft: 4 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
TSX

echo "→ Icon test route to verify glyphs render"
mkdir -p "app/_shelf"
cat > "app/_shelf/icon-test.tsx" <<'TSX'
import { View, Text, ScrollView } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';

export default function IconTest() {
  const names = [
    'settings-outline','share-outline','stats-chart-outline','albums-outline',
    'add-circle-outline','cart-outline','chevron-down','close','checkmark',
    'image-outline','search-outline','shield-outline'
  ];
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Text style={{ fontWeight: '800', fontSize: 18 }}>Ionicons Sanity Check</Text>
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

echo "→ Clear Metro cache dirs (safe) so the icon font reloads"
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true

echo "✅ Done. Next: npm i  &&  npx expo start --tunnel --clear"
echo "Then visit  /_shelf/icon-test  to confirm glyphs."
