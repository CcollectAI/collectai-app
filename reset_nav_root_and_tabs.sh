#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

ROOT_LAYOUT="app/_layout.tsx"
TABS_LAYOUT="app/(tabs)/_layout.tsx"

echo "=== Resetting root app/_layout.tsx to a simple Stack (no Tabs) ==="
if [ -f "$ROOT_LAYOUT" ]; then
  BAK_ROOT="${ROOT_LAYOUT}.bak_nav_reset_$(date +%Y%m%d-%H%M%S)"
  cp "$ROOT_LAYOUT" "$BAK_ROOT"
  echo "📦 Backed up existing root layout to:"
  echo "   $BAK_ROOT"
fi

cat > "$ROOT_LAYOUT" <<'TSX'
import React from "react";
import { Stack } from "expo-router";

/**
 * Root layout:
 * - Stack only, NO bottom tabs here.
 * - The (tabs) group inside app/(tabs)/_layout.tsx is responsible for the tab bar.
 */
export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }} />
  );
}
TSX

echo "✅ Root layout now uses Stack only (no Tabs)."

echo
echo "=== Resetting app/(tabs)/_layout.tsx to exactly 4 tabs ==="
if [ -f "$TABS_LAYOUT" ]; then
  BAK_TABS="${TABS_LAYOUT}.bak_nav_reset_$(date +%Y%m%d-%H%M%S)"
  cp "$TABS_LAYOUT" "$BAK_TABS"
  echo "📦 Backed up existing tabs layout to:"
  echo "   $BAK_TABS"
fi

cat > "$TABS_LAYOUT" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Bottom tab layout:
 *
 * Exactly 4 tabs, in this order:
 *  - index        -> "Portfolio"     (app/(tabs)/index.tsx)
 *  - items        -> "Items"         (app/(tabs)/items.tsx)
 *  - add          -> "Add"           (app/(tabs)/add.tsx)
 *  - marketplace  -> "Search"        (app/(tabs)/marketplace.tsx)
 *
 * NOTE:
 *  - app/(tabs)/portfolio.tsx may exist for deep links (/portfolio)
 *    but is NOT declared as a tab here.
 */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarLabelStyle: { fontSize: 11 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="pie-chart-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="add-circle-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: "Search",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="search-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
TSX

echo "✅ Tabs layout now has only 4 tabs: [index, items, add, marketplace]."

echo
echo "=== Done. Root layout = Stack, (tabs) layout = 4 Tabs. ==="
