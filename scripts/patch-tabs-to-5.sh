#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/_layout.tsx"

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found. Aborting."
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.bak_${TS}"

cat > "$FILE" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,            // remove title banner in tabs
        tabBarShowLabel: true,         // show printed words under icons
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "700",
        },
        tabBarStyle: {
          height: 74,
          paddingTop: 8,
          paddingBottom: 10,
        },
      }}
    >
      {/* EXACTLY 5 tabs: Portfolio | Items | Add | Events | Search */}
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarLabel: "Portfolio",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "stats-chart" : "stats-chart-outline"}
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarLabel: "Items",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "albums" : "albums-outline"}
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarLabel: "Add",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "add-circle" : "add-circle-outline"}
              size={size + 6}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="events"
        options={{
          title: "Events",
          tabBarLabel: "Events",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "calendar" : "calendar-outline"}
              size={size}
              color={color}
            />
          ),
        }}
      />

      {/* Replace any “Chat” concept with Search (magnifying glass) */}
      <Tabs.Screen
        name="search"
        options={{
          title: "Search",
          tabBarLabel: "Search",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "search" : "search-outline"}
              size={size}
              color={color}
            />
          ),
        }}
      />

      {/* Safety: if any extra routes exist in (tabs), hide them from the tab bar */}
      <Tabs.Screen name="chat" options={{ href: null }} />
      <Tabs.Screen name="marketplace" options={{ href: null }} />
      <Tabs.Screen name="explore" options={{ href: null }} />
      <Tabs.Screen name="categories" options={{ href: null }} />
      <Tabs.Screen name="listings" options={{ href: null }} />
      <Tabs.Screen name="events-drops" options={{ href: null }} />
    </Tabs>
  );
}
TSX

echo "OK: Patched tabs layout to 5 fixed tabs"
echo "Backup: ${FILE}.bak_${TS}"
