#!/usr/bin/env bash
set -euo pipefail

echo "→ Install icons + font (fixes '?' placeholders)"
npx expo install @expo/vector-icons expo-font >/dev/null

echo "→ Ensure icons font loads at app start"
mkdir -p app
if [ -f app/_layout.tsx ]; then cp app/_layout.tsx app/_layout.tsx.bak; fi
cat > app/_layout.tsx <<'TSX'
import { Stack } from 'expo-router';
import { useEffect } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  // Load Ionicons so icons don't render as '?'.
  const [fontsLoaded] = useFonts(Ionicons.font);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(()=>{});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card }, // white header line
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

echo "→ Create/replace anchored CompactSelect (popover under trigger, scrollable)"
mkdir -p src/components
if [ -f src/components/CompactSelect.tsx ]; then cp src/components/CompactSelect.tsx src/components/CompactSelect.tsx.bak; fi
cat > src/components/CompactSelect.tsx <<'TSX'
import { useRef, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

type Props = {
  title?: string;
  value?: string | null;
  options: string[];
  placeholder?: string;
  onChange: (v: string) => void;
  searchable?: boolean;
};

export default function CompactSelect({
  title,
  value,
  options,
  placeholder = 'Select…',
  onChange,
  searchable = false,
}: Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const show = () => {
    // Measure trigger position on screen, then open the popover just under it.
    try {
      // @ts-ignore measureInWindow exists at runtime
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

  const filtered = query
    ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase()))
    : options;

  const { width: SW, height: SH } = Dimensions.get('window');
  const POPOVER_W = 260; // tidy fixed width
  const left = Math.max(8, Math.min((anch?.x ?? 16), SW - POPOVER_W - 8));
  const topBase = (anch ? anch.y + anch.h + 6 : 120);
  const maxH = Math.max(160, Math.min(320, SH - topBase - 16));
  const top = Math.min(topBase, SH - maxH - 8);

  return (
    <>
      {/* Compact trigger: tiny white box around the word only */}
      <Pressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }}>
        <View
          style={{
            backgroundColor: theme.colors.card,
            borderWidth: 1,
            borderColor: theme.colors.border,
            paddingVertical: theme.spacing.xs,
            paddingHorizontal: theme.spacing.sm,
            flexDirection: 'row',
            alignItems: 'center',
            gap: theme.spacing.xs,
          }}
        >
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>
            {value || placeholder}
          </Text>
          <Ionicons name="chevron-down" size={14} color={theme.colors.subtext} />
        </View>
      </Pressable>

      {/* Anchored popover */}
      <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
        <Pressable
          onPress={hide}
          style={{
            flex: 1,
            backgroundColor: 'rgba(11,61,145,0.05)', // very light overlay (not dark)
          }}
        >
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
                <Ionicons name="close" size={18} color={theme.colors.subtext} />
              </View>
            ) : null}

            {searchable ? (
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="Search…"
                placeholderTextColor={theme.colors.subtext}
                style={{
                  borderWidth: 1,
                  borderColor: theme.colors.border,
                  padding: theme.spacing.sm,
                  backgroundColor: '#fff',
                  marginBottom: theme.spacing.sm,
                }}
              />
            ) : null}

            <ScrollView keyboardShouldPersistTaps="handled">
              {filtered.map((opt, idx) => {
                const selected = value === opt;
                return (
                  <Pressable
                    key={opt}
                    onPress={() => {
                      onChange(opt);
                      hide();
                    }}
                  >
                    <View
                      style={{
                        paddingVertical: theme.spacing.md,
                        flexDirection: 'row',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderTopWidth: idx === 0 ? 0 : 1,
                        borderColor: theme.colors.border,
                      }}
                    >
                      <Text style={{ color: theme.colors.navy, fontWeight: selected ? '800' : '600' }}>
                        {opt}
                      </Text>
                      {selected ? (
                        <Ionicons name="checkmark" size={16} color={theme.colors.navy} />
                      ) : null}
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

echo "→ Done. Icons module installed, fonts loaded, dropdown now anchors under trigger."
