#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "→ Install SVG icon stack (no fonts needed)"
npx expo install lucide-react-native react-native-svg >/dev/null

echo "→ Create a drop-in Icon shim that understands your Ionicon names"
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
  Shield,       // shield-outline
} from 'lucide-react-native';

type Props = { name:
  | 'stats-chart-outline' | 'albums-outline' | 'add-circle-outline' | 'cart-outline'
  | 'settings-outline' | 'share-outline' | 'chevron-down' | 'close'
  | 'checkmark' | 'image-outline' | 'search-outline' | 'shield-outline';
  size?: number; color?: string;
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

echo "→ Use SVG Icon shim in tabs layout (replaces Ionicons everywhere)"
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
          tabBarIcon: ({ color, size }) => <Icon name="stats-chart-outline" />,
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

echo "→ Swap other components to the SVG Icon shim"
# CompactSelect
[ -f "src/components/CompactSelect.tsx" ] && cp "src/components/CompactSelect.tsx" "src/components/CompactSelect.tsx.bak.$ts"
cat > "src/components/CompactSelect.tsx" <<'TSX'
import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import Icon from '@/components/Icon';
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
        setAnch({ x, y, w, h }); setOpen(true);
      });
    } catch { setAnch(null); setOpen(true); }
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
          <Icon name="chevron-down" />
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
                <Icon name="close" />
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
                      {selected ? <Icon name="checkmark" /> : null}
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

# SearchRow
[ -f "src/components/SearchRow.tsx" ] && cp "src/components/SearchRow.tsx" "src/components/SearchRow.tsx.bak.$ts"
cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';

export default function SearchRow({ title, subtitle, price, badge, thumbUri }: {
  title: string; subtitle: string; price: string; badge?: string; thumbUri?: string | null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.md }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <Icon name="image-outline" />}
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

# ShieldBadge
[ -f "src/components/ShieldBadge.tsx" ] && cp "src/components/ShieldBadge.tsx" "src/components/ShieldBadge.tsx.bak.$ts"
cat > "src/components/ShieldBadge.tsx" <<'TSX'
import { View, Text } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';
const COLORS: Record<Tier, string> = { silver: '#C0C0C0', gold: '#D4AF37', platinum: '#B0BEC5' };

export default function ShieldBadge({ tier }: { tier: Tier }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', borderWidth: 1, borderColor: COLORS[tier], paddingVertical: 2, paddingHorizontal: 6 }}>
      <Icon name="shield-outline" />
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12, marginLeft: 4 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
TSX

echo "→ Make icon-test use the SVG shim too (guarantees visible)"
mkdir -p app/_shelf
[ -f "app/_shelf/icon-test.tsx" ] && cp "app/_shelf/icon-test.tsx" "app/_shelf/icon-test.tsx.bak.$ts"
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
      <Text style={{ color: '#64748B' }}>These are SVG icons (no font). If you see them, the app is fixed.</Text>
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

echo "→ QUICK BACKUP (commit + tag + lightweight tarball)"
git add -A || true
git commit -m "[backup $ts] before switching to SVG icons" || true
git tag -f "backup-$ts" || true
mkdir -p backups
tar -czf backups/collectai-backup-$ts.tar.gz . \
  --exclude='./backups/*.tar.gz' \
  --exclude='./node_modules' \
  --exclude='./.expo' \
  --exclude='./.git' || true
echo "✔ Backup TAR: backups/collectai-backup-$ts.tar.gz"

echo "→ Clean Metro caches and restart hint"
rm -rf .expo /tmp/metro-* ~/.cache/expo 2>/dev/null || true
echo "✅ Now run: npx expo start --tunnel --clear  (then tap 'Icon Test')"
