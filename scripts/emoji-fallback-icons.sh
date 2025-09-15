#!/usr/bin/env bash
set -euo pipefail

echo "→ Add EmojiIcon (simple, reliable emoji-based icons)"
mkdir -p src/components
cat > src/components/EmojiIcon.tsx <<'TSX'
import { Text } from 'react-native';

export type EmojiGlyph =
  | 'settings' | 'chart' | 'items' | 'add' | 'cart' | 'share'
  | 'chevron-down' | 'close' | 'check' | 'image' | 'search';

const MAP: Record<EmojiGlyph, string> = {
  settings: '⚙️',
  chart: '📈',
  items: '🗂️',
  add: '➕',
  cart: '🛒',
  share: '📤',
  'chevron-down': '▾',
  close: '✖️',
  check: '✅',
  image: '🖼️',
  search: '🔍',
};

export default function EmojiIcon({ name, size = 18 }: { name: EmojiGlyph; size?: number }) {
  const glyph = MAP[name] ?? '•';
  return <Text style={{ fontSize: size, lineHeight: size + 2 }}>{glyph}</Text>;
}
TSX

echo "→ Make ShieldBadge use emoji (no Ionicons needed)"
cat > src/components/ShieldBadge.tsx <<'TSX'
import { View, Text } from 'react-native';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';

const COLORS: Record<Tier, string> = {
  silver: '#C0C0C0',
  gold: '#D4AF37',
  platinum: '#E5E4E2',
};

export default function ShieldBadge({ tier }: { tier: Tier }) {
  return (
    <View style={{
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#fff',
      borderWidth: 1,
      borderColor: COLORS[tier],
      paddingVertical: 2,
      paddingHorizontal: 6,
    }}>
      <Text style={{ marginRight: 4 }}>🛡️</Text>
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
TSX

echo "→ Update Tabs to use EmojiIcon"
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Pressable, Share } from 'react-native';
import { theme } from '@/theme';
import EmojiIcon from '@/components/EmojiIcon';

function SettingsButton() {
  return (
    <Link href="/_shelf/settings" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <EmojiIcon name="settings" size={18} />
      </Pressable>
    </Link>
  );
}
function ShareButton() {
  const onShare = async () => { try { await Share.share({ message: 'Shared from Collect AI' }); } catch {} };
  return (
    <Pressable onPress={onShare} style={{ paddingHorizontal: 12 }}>
      <EmojiIcon name="share" size={18} />
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
          tabBarIcon: ({ size }) => <EmojiIcon name="chart" size={size} />,
          headerRight: () => <SettingsButton />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarLabel: 'Items',
          tabBarIcon: ({ size }) => <EmojiIcon name="items" size={size} />,
          headerRight: () => <ShareButton />,
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: ({ size }) => <EmojiIcon name="add" size={size} />,
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: 'Marketplace',
          tabBarIcon: ({ size }) => <EmojiIcon name="cart" size={size} />,
        }}
      />
    </Tabs>
  );
}
TSX

echo "→ CompactSelect: swap Ionicons for EmojiIcon"
[ -f "src/components/CompactSelect.tsx" ] && cp "src/components/CompactSelect.tsx" "src/components/CompactSelect.tsx.bak"
cat > "src/components/CompactSelect.tsx" <<'TSX'
import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import { theme } from '@/theme';
import EmojiIcon from '@/components/EmojiIcon';

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
          <EmojiIcon name="chevron-down" size={14} />
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
                <EmojiIcon name="close" size={16} />
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
                      {selected ? <EmojiIcon name="check" size={16} /> : null}
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

echo "→ SearchRow: emoji for image placeholder"
[ -f "src/components/SearchRow.tsx" ] && cp "src/components/SearchRow.tsx" "src/components/SearchRow.tsx.bak"
cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import EmojiIcon from '@/components/EmojiIcon';
import { theme } from '@/theme';

export default function SearchRow({ title, subtitle, price, badge, thumbUri }: {
  title: string; subtitle: string; price: string; badge?: string; thumbUri?: string | null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.md }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <EmojiIcon name="image" size={18} />}
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

echo "→ Marketplace: replace search icon with emoji"
[ -f "app/(tabs)/marketplace.tsx" ] && cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak"
perl -0777 -pe "s/import\\s*\\{\\s*Ionicons\\s*\\}\\s*from\\s*'@expo\\/vector-icons';\\n//g" -i "app/(tabs)/marketplace.tsx" || true
perl -0777 -pe "s/<Ionicons name=\"search-outline\"[^>]*\\/>/<EmojiIcon name=\"search\" size={18} \/>/g" -i "app/(tabs)/marketplace.tsx" || true
# ensure EmojiIcon import exists
grep -q "EmojiIcon" app/(tabs)/marketplace.tsx || sed -i "1i import EmojiIcon from '@/components/EmojiIcon';" app/(tabs)/marketplace.tsx

echo "→ Items screen: share icon -> emoji"
[ -f "app/(tabs)/items.tsx" ] && cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"
perl -0777 -pe "s/import\\s*\\{\\s*Ionicons\\s*\\}\\s*from\\s*'@expo\\/vector-icons';\\n//g" -i "app/(tabs)/items.tsx" || true
perl -0777 -pe "s/<Ionicons name=\"share-outline\"[^>]*\\/>/<EmojiIcon name=\"share\" size={16} \/>/g" -i "app/(tabs)/items.tsx" || true
grep -q "EmojiIcon" app/(tabs)/items.tsx || sed -i "1i import EmojiIcon from '@/components/EmojiIcon';" app/(tabs)/items.tsx

echo "→ CompactSelect & Tabs already updated. Done."
