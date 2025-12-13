#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

LAYOUT_FILE="app/(tabs)/_layout.tsx"

echo "=== Hard-fixing _layout.tsx to only show 4 tabs (Portfolio, Items, Add, Search) ==="

if [ -f "$LAYOUT_FILE" ]; then
  BAK="${LAYOUT_FILE}.bak_hardfix_$(date +%Y%m%d-%H%M%S)"
  cp "$LAYOUT_FILE" "$BAK"
  echo "📦 Backed up existing _layout.tsx to:"
  echo "  $BAK"
fi

cat > "$LAYOUT_FILE" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Main bottom tab layout.
 *
 * Visible tabs (left to right):
 *  - portfolio  -> "Portfolio"
 *  - items      -> "Items"
 *  - add        -> "Add"
 *  - marketplace-> "Search" (search icon)
 *
 * Hidden routes:
 *  - index      -> href: null, tabBarButton: () => null
 *  - search     -> href: null, tabBarButton: () => null
 */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarLabelStyle: { fontSize: 11 },
      }}
    >
      {/* Hidden stray routes (make sure they never show as tabs) */}
      <Tabs.Screen
        name="index"
        options={{
          href: null,
          tabBarButton: () => null,
        }}
      />
      <Tabs.Screen
        name="search"
        options={{
          href: null,
          tabBarButton: () => null,
        }}
      />

      {/* Visible tabs */}
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

echo "✅ _layout.tsx now explicitly hides 'index' and 'search' routes and only shows 4 tabs."
