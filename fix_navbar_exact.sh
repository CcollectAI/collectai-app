#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

LAYOUT_FILE="app/(tabs)/_layout.tsx"

echo "=== Fixing bottom nav: Portfolio, Items, Add, Search (Marketplace screen) ==="

if [ -f "$LAYOUT_FILE" ]; then
  BAK="${LAYOUT_FILE}.bak_navfix_$(date +%Y%m%d-%H%M%S)"
  cp "$LAYOUT_FILE" "$BAK"
  echo "  Backed up existing _layout.tsx to:"
  echo "    $BAK"
fi

cat > "$LAYOUT_FILE" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Main bottom tab layout.
 * Exactly 4 tabs, in this order: Portfolio, Items, Add, Search.
 *
 * NOTE:
 *  - The "Search" tab reuses the existing "marketplace" route file,
 *    but shows as "Search" with a magnifying glass.
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
        name="portfolio"
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

echo "  ✅ Nav now: [Portfolio, Items, Add, Search] where Search uses 'marketplace' route."
echo "=== Done. ==="
