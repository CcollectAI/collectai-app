set -euo pipefail
ts="$(date +%Y%m%d-%H%M%S)"

echo "== autosave =="
git add -A || true
git commit -m "autosave pre fast-nav-fix $ts" || true
git tag -f autosave-latest || true
git branch -f autosave-$ts || true

echo "== dirs =="
mkdir -p app "(tabs)" >/dev/null 2>&1 || true
mkdir -p app/(tabs) src src/auth app/_shelf/moved-$ts

echo "== root layout (expo-router only) =="
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

echo "== tabs layout (4 tabs only) =="
cat > app/(tabs)/_layout.tsx <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#0B3D91",
        tabBarInactiveTintColor: "#94A3B8",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="wallet-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cube-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="add-circle" color={color} size={Math.round(size * 1.15)} />
          ),
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: "Marketplace",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="bag-handle-outline" color={color} size={size} />
          ),
        }}
      />
    </Tabs>
  );
}
TSX

echo "== NotFound =="
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

echo "== theme stub (if missing) =="
if [ ! -f src/theme.ts ]; then
cat > src/theme.ts <<'TS'
export const theme = {
  colors: {
    bg: "#E6F7F8",        // Tiffany blue background
    card: "#FFFFFF",      // White cards
    text: "#0B3D91",      // Navy text
    subtext: "#4B5563",
    brand: { base: "#0BBBD6" },
    border: "#E5E7EB",
    up: "#16A34A",
    down: "#DC2626",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { none: 0, sm: 4, md: 8, lg: 12, xl: 16 },
};
export default theme;
TS
fi

echo "== auth/session stub (if missing) =="
if [ ! -f src/auth/session.ts ]; then
cat > src/auth/session.ts <<'TS'
export type SessionState = { ready: boolean; signedIn: boolean };
export function useSession(): SessionState {
  // Safe placeholder
  return { ready: true, signedIn: false };
}
TS
fi

echo "== minimal screens (only if missing) =="
# Portfolio
if [ ! -f app/(tabs)/index.tsx ]; then
cat > app/(tabs)/index.tsx <<'TSX'
import React from "react";
import { View, Text, SafeAreaView, ScrollView } from "react-native";
import theme from "../../src/theme";

export default function PortfolioScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>
          Collection Value
        </Text>
        <View style={{ backgroundColor: theme.colors.card, borderColor: theme.colors.border, borderWidth: 1, padding: 16 }}>
          <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text }}>€ 2,752.00</Text>
          <Text style={{ color: theme.colors.up, marginTop: 4 }}>+3.10% today</Text>
        </View>
        <View style={{ backgroundColor: theme.colors.card, borderColor: theme.colors.border, borderWidth: 1, padding: 16 }}>
          <Text style={{ fontSize: 18, fontWeight: "700", color: theme.colors.text, marginBottom: 8 }}>Collection</Text>
          <Text style={{ color: theme.colors.subtext }}>Sample rows will go here…</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
TSX
fi

# Items
if [ ! -f app/(tabs)/items.tsx ]; then
cat > app/(tabs)/items.tsx <<'TSX'
import React from "react";
import { SafeAreaView, ScrollView, View, Text } from "react-native";
import theme from "../../src/theme";

export default function ItemsScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>Items</Text>
        <View style={{ backgroundColor: theme.colors.card, borderColor: theme.colors.border, borderWidth: 1, padding: 16 }}>
          <Text style={{ color: theme.colors.subtext }}>Your items by category…</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
TSX
fi

# Add
if [ ! -f app/(tabs)/add.tsx ]; then
cat > app/(tabs)/add.tsx <<'TSX'
import React from "react";
import { SafeAreaView, View, Text } from "react-native";
import theme from "../../src/theme";

export default function AddScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>Add Item</Text>
        <Text style={{ marginTop: 8, color: theme.colors.subtext }}>Form coming next…</Text>
      </View>
    </SafeAreaView>
  );
}
TSX
fi

# Marketplace
if [ ! -f app/(tabs)/marketplace.tsx ]; then
cat > app/(tabs)/marketplace.tsx <<'TSX'
import React, { useState } from "react";
import { SafeAreaView, View, Text, Pressable } from "react-native";
import theme from "../../src/theme";

export default function MarketplaceScreen() {
  const [tab, setTab] = useState<"chat"|"search"|"sell">("chat");
  const Seg = ({label, val}:{label:string; val:"chat"|"search"|"sell"}) => (
    <Pressable onPress={() => setTab(val)} style={{
      paddingVertical: 8, paddingHorizontal: 12,
      borderWidth: 1, borderColor: theme.colors.border,
      backgroundColor: tab===val ? theme.colors.card : "transparent"
    }}>
      <Text style={{ color: theme.colors.text, fontWeight: tab===val ? "800":"600" }}>{label}</Text>
    </Pressable>
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16, gap: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>Marketplace</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Seg label="Chat" val="chat" /><Seg label="Search" val="search" /><Seg label="Sell" val="sell" />
        </View>
        <View style={{ backgroundColor: theme.colors.card, borderColor: theme.colors.border, borderWidth: 1, padding: 16 }}>
          <Text style={{ color: theme.colors.subtext }}>[{tab.toUpperCase()}] content placeholder…</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}
TSX
fi

echo "== move extra demo/legacy routes out of router (shelved) =="
for p in \
  "app/(tabs)/explore.tsx" \
  "app/(tabs)/categories" \
  "app/(tabs)/collection" \
  "app/(tabs)/listings" \
  "app/(tabs)/post" \
  "app/(auth)" \
; do
  if [ -e "$p" ]; then
    mv "$p" "app/_shelf/moved-$ts/" && echo "moved $p -> app/_shelf/moved-$ts/"
  fi
done

echo "== dedupe =="
npm dedupe || true

echo "== done =="
echo "Run:"
echo "  EXPO_USE_DEV_SERVER=true npx expo start --tunnel --clear"
