#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "==== DISK BEFORE ===="
df -h || true
echo

echo "→ Stop Expo/Metro and free ports"
pkill -f "expo start" 2>/dev/null || true
pkill -f "[m]etro"     2>/dev/null || true
sudo fuser -k 19000/tcp 19001/tcp 8081/tcp 2>/dev/null || true

echo "→ Show biggest things in repo (top 12)"
du -xh --max-depth=1 . | sort -h | tail -n 12 || true
echo

echo "→ Remove heavy dev folders (safe)"
rm -rf node_modules .expo .turbo .next dist build coverage .cache 2>/dev/null || true
rm -rf android/.gradle android/build ios/Pods ios/build 2>/dev/null || true

echo "→ Remove old backups except the most recent tarball (keeps the newest 1)"
ls -1t backups/*.tar.gz 2>/dev/null | tail -n +2 | xargs -r rm -f

echo "→ Clear user caches"
rm -rf ~/.npm ~/.cache/npm ~/.cache/expo ~/.expo ~/.yarn ~/.cache/yarn ~/.pnpm-store /tmp/metro-* /tmp/npmcache 2>/dev/null || true

echo "→ Clean logs & apt caches"
sudo journalctl --vacuum-time=2d 2>/dev/null || true
sudo apt-get clean               2>/dev/null || true
sudo rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* 2>/dev/null || true

echo "→ Prune old Node versions (keeps the one currently used, if nvm exists)"
if [ -d "$HOME/.nvm/versions/node" ]; then
  cur="$(node -v 2>/dev/null || echo '')"
  for d in "$HOME/.nvm/versions/node"/*; do
    [ -d "$d" ] || continue
    base="$(basename "$d")"
    if [ "v$base" = "$cur" ] || [ "$base" = "$cur" ]; then
      echo "  keep $base"
    else
      echo "  remove $base"
      rm -rf "$d"
    fi
  done
fi

echo
echo "==== DISK AFTER CLEAN ===="
df -h || true
echo

echo "→ Reinstall deps fresh (quiet)"
npm i --no-audit --no-fund

echo "→ Install SVG icon stack (no fonts) — uses far less than vector fonts"
npx expo install react-native-svg lucide-react-native

echo "→ Write SVG Icon shim and wire it in Tabs + components"
mkdir -p src/components

# Icon shim
cat > src/components/Icon.tsx <<'TSX'
import React from 'react';
import {
  LineChart, Images, PlusCircle, ShoppingCart, Settings, Share2,
  ChevronDown, X, Check, Image as ImageIcon, Search, Shield
} from 'lucide-react-native';

type Name =
  | 'stats-chart-outline' | 'albums-outline' | 'add-circle-outline' | 'cart-outline'
  | 'settings-outline' | 'share-outline' | 'chevron-down' | 'close'
  | 'checkmark' | 'image-outline' | 'search-outline' | 'shield-outline';

export default function Icon({ name, size = 20, color = '#0B3D91' }:{name:Name; size?:number; color?:string}) {
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

# Tabs layout -> use Icon shim
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

# SearchRow -> Icon shim
if [ -f "src/components/SearchRow.tsx" ]; then
  cp "src/components/SearchRow.tsx" "src/components/SearchRow.tsx.bak.$ts"
  cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
export default function SearchRow({ title, subtitle, price, badge, thumbUri }:{
  title:string; subtitle:string; price:string; badge?:string; thumbUri?:string|null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: 12 }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <Icon name="image-outline" />}
      </View>
      <View style={{ flex: 1, paddingRight: 12 }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '600' }} numberOfLines={1}>{title}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }} numberOfLines={1}>{subtitle}</Text>
        {badge ? <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>{badge}</Text> : null}
      </View>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{price}</Text>
    </View>
  );
}
TSX
fi

# CompactSelect -> Icon shim
if [ -f "src/components/CompactSelect.tsx" ]; then
  cp "src/components/CompactSelect.tsx" "src/components/CompactSelect.tsx.bak.$ts"
  cat > "src/components/CompactSelect.tsx" <<'TSX'
import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
type Props = { title?:string; value?:string|null; options:string[]; placeholder?:string; onChange:(v:string)=>void; searchable?:boolean; };
export default function CompactSelect({ title, value, options, placeholder='Select…', onChange, searchable=false }:Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{x:number;y:number;w:number;h:number}|null>(null);
  const show = () => { try { // @ts-ignore
    triggerRef.current?.measureInWindow?.((x:number,y:number,w:number,h:number)=>{ setAnch({x,y,w,h}); setOpen(true); }); } catch { setAnch(null); setOpen(true); } };
  const hide = () => setOpen(false);
  const filtered = query ? options.filter(o=>o.toLowerCase().includes(query.toLowerCase())) : options;
  const { width:SW, height:SH } = Dimensions.get('window'); const POPOVER_W=260; const left=Math.max(8, Math.min((anch?.x ?? 16), SW-POPOVER_W-8)); const topBase=(anch ? anch.y+anch.h+6 : 120); const maxH=Math.max(160, Math.min(320, SH-topBase-16)); const top=Math.min(topBase, SH-maxH-8);
  return (<>
    <Pressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }}>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, paddingVertical: 4, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{value || placeholder}</Text>
        <Icon name="chevron-down" />
      </View>
    </Pressable>
    <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
      <Pressable onPress={hide} style={{ flex:1, backgroundColor:'rgba(11,61,145,0.05)' }}>
        <Pressable onPress={()=>{}} style={{ position:'absolute', top, left, width:POPOVER_W, backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding:12, maxHeight:maxH }}>
          {title ? (<View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
            <Text style={{ color: theme.colors.navy, fontWeight:'800' }}>{title}</Text>
            <Icon name="close" />
          </View>) : null}
          {searchable ? (
            <TextInput value={query} onChangeText={setQuery} placeholder="Search…" placeholderTextColor={theme.colors.subtext} style={{ borderWidth:1, borderColor: theme.colors.border, padding:8, backgroundColor:'#fff', marginBottom:8 }} />
          ) : null}
          <ScrollView keyboardShouldPersistTaps="handled">
            {filtered.map((opt, idx) => {
              const selected = value === opt;
              return (
                <Pressable key={opt} onPress={()=>{ onChange(opt); hide(); }}>
                  <View style={{ paddingVertical:12, flexDirection:'row', alignItems:'center', justifyContent:'space-between', borderTopWidth: idx===0?0:1, borderColor: theme.colors.border }}>
                    <Text style={{ color: theme.colors.navy, fontWeight: selected?'800':'600' }}>{opt}</Text>
                    {selected ? <Icon name="checkmark" /> : null}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  </>);
}
TSX
fi

# Icon test screen
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
      <Text style={{ color: '#64748B' }}>No fonts used. If you see icons below, we’re done.</Text>
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

echo "→ Final disk check"
df -h || true
echo
echo "✅ Cleanup + SVG icons wired. Next step starts Expo."
echo "   npx expo start --tunnel --clear"
echo "Then tap 'Icon Test' on the Portfolio header."
