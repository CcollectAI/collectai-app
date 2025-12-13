#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
LAYOUT_FILE="$PROJECT_ROOT/app/(tabs)/_layout.tsx"
BACKUP_FILE="$LAYOUT_FILE.bak_calendar_tabs_$(date +%s)"

cd "$PROJECT_ROOT"

if [ -f "$LAYOUT_FILE" ]; then
  cp "$LAYOUT_FILE" "$BACKUP_FILE"
  echo "📦 Backed up existing _layout.tsx to:"
  echo "  $BACKUP_FILE"
fi

cat > "$LAYOUT_FILE" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Main bottom tab layout.
 * Fixed 4 tabs only: Portfolio, Items, Add, Search.
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
        name="search"
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

echo "✅ Tabs layout updated to: Portfolio, Items, Add, Search."
