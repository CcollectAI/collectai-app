#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

LAYOUT_FILE="app/(tabs)/_layout.tsx"

echo "=== Hard-resetting app/(tabs)/_layout.tsx to exactly 4 tabs ==="

if [ -f "$LAYOUT_FILE" ]; then
  BAK="${LAYOUT_FILE}.bak_nav_reset_$(date +%Y%m%d-%H%M%S)"
  cp "$LAYOUT_FILE" "$BAK"
  echo "📦 Backed up existing _layout.tsx to:"
  echo "   $BAK"
fi

cat > "$LAYOUT_FILE" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Bottom tab layout
 *
 * Exactly 4 tabs in this order:
 *  - index        -> "Portfolio"
 *  - items        -> "Items"
 *  - add          -> "Add"
 *  - marketplace  -> "Search"
 *
 * NOTE:
 *  - 'index' uses app/(tabs)/index.tsx (your main portfolio + watchlist screen)
 *  - 'portfolio.tsx' exists only for deep links and is NOT a tab here
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

echo "✅ app/(tabs)/_layout.tsx now defines exactly 4 tabs: [index, items, add, marketplace]."
