#!/usr/bin/env bash
set -euo pipefail

TABS="app/(tabs)/_layout.tsx"
PORT="app/(tabs)/index.tsx"
SEARCH="app/(tabs)/search.tsx"
ROOT="app/_layout.tsx"

need() { [ -f "$1" ] || { echo "ERROR: missing $1"; exit 1; }; }
need "$TABS"
need "$PORT"
need "$SEARCH"
need "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"

# Backups (non-destructive)
cp "$TABS"   "${TABS}.pre_fix_${TS}"
cp "$PORT"   "${PORT}.pre_fix_${TS}"
cp "$SEARCH" "${SEARCH}.pre_fix_${TS}"
cp "$ROOT"   "${ROOT}.pre_fix_${TS}"

# 1) Restore a richer Portfolio that won't crash (hover chart already removed)
# Prefer latest remove_hoverchart backup.
PORT_BAK="$(ls -1t app/\(tabs\)/index.tsx.bak_remove_hoverchart_* 2>/dev/null | head -n 1 || true)"
if [ -z "$PORT_BAK" ]; then
  echo "ERROR: No index.tsx.bak_remove_hoverchart_* found. Aborting."
  exit 1
fi
echo "Restoring Portfolio from: $PORT_BAK"
cp "$PORT_BAK" "$PORT"

# 2) Restore Search from best available backup (no 20251212 exists)
# Prefer the .bak.20251213_171154 one you have.
if [ -f "app/(tabs)/search.tsx.bak.20251213_171154" ]; then
  echo "Restoring Search from: app/(tabs)/search.tsx.bak.20251213_171154"
  cp "app/(tabs)/search.tsx.bak.20251213_171154" "$SEARCH"
elif [ -f "app/(tabs)/search.tsx.bak_20251213_145358" ]; then
  echo "Restoring Search from: app/(tabs)/search.tsx.bak_20251213_145358"
  cp "app/(tabs)/search.tsx.bak_20251213_145358" "$SEARCH"
else
  echo "WARN: No Search backups found; leaving current search.tsx as-is."
fi

# 3) Rewrite tabs layout to EXACTLY the routes that actually exist in your folder:
# index.tsx, items.tsx, add.tsx, events.tsx, search.tsx
# Hide marketplace tab (still accessible via route, but not shown in tab bar).
cat > "$TABS" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,                 // remove title banner
        tabBarShowLabel: true,              // words under icons
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: { fontSize: 11, fontWeight: "700" },
        tabBarIconStyle: { marginTop: 2 },
        tabBarStyle: {
          height: 70,
          paddingTop: 8,
          paddingBottom: 10,
          backgroundColor: "#FFFFFF",
          borderTopWidth: 1,
          borderTopColor: "rgba(11,31,58,0.10)",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarLabel: "Portfolio",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "pie-chart" : "pie-chart-outline"}
              size={Math.max(18, size - 4)}   // smaller icons
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
              size={Math.max(18, size - 4)}
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
              size={Math.max(22, size)}       // keep Add slightly more prominent
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
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="search"
        options={{
          title: "Search",
          tabBarLabel: "Search",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "search" : "search-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      {/* Hide extra routes from the tab bar to avoid “6 tabs” */}
      <Tabs.Screen name="marketplace" options={{ href: null }} />
    </Tabs>
  );
}
TSX

# 4) Optional: also remove headers at root (keeps no title banners anywhere)
# If your root layout needs more logic, we keep it minimal but safe.
cat > "$ROOT" <<'TSX'
import React from "react";
import { Stack } from "expo-router";

export default function RootLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
TSX

echo "OK: Restored real Portfolio + restored Search + fixed tab bar (labels, smaller icons, styled bar, 5 tabs)"
echo "Backups created:"
echo " - ${TABS}.pre_fix_${TS}"
echo " - ${PORT}.pre_fix_${TS}"
echo " - ${SEARCH}.pre_fix_${TS}"
echo " - ${ROOT}.pre_fix_${TS}"
