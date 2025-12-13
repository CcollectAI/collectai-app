#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== Fixing tab layout + entry + /home/portfolio route ==="

TABS_LAYOUT="app/(tabs)/_layout.tsx"
INDEX_FILE="app/index.tsx"
HOME_DIR="app/home"
HOME_PORTFOLIO_FILE="$HOME_DIR/portfolio.tsx"

# 1) Ensure tab screens exist (but don't overwrite them if they already do)
ensure_tab_screen() {
  local name="$1"
  local file="app/(tabs)/${name}.tsx"
  local label="$2"

  if [ -f "$file" ]; then
    echo "  ✓ Found existing tab screen: $file"
    return 0
  fi

  echo "  ⚠️  Tab screen missing, creating minimal placeholder: $file"
  cat > "$file" <<TSX
import React from "react";
import { View, Text } from "react-native";

export default function ${name[0]^}${name:1}Screen() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <Text>${label} screen</Text>
    </View>
  );
}
TSX
}

echo "-> Ensuring tab screens exist (won't overwrite real ones)..."
ensure_tab_screen "portfolio" "Portfolio"
ensure_tab_screen "items" "Items"
ensure_tab_screen "add" "Add"
ensure_tab_screen "search" "Search"
echo

# 2) Fix tabs layout: Portfolio, Items, Add, Search (in that order)
if [ -f "$TABS_LAYOUT" ]; then
  TABS_BAK="${TABS_LAYOUT}.bak_fixnav_$(date +%Y%m%d-%H%M%S)"
  cp "$TABS_LAYOUT" "$TABS_BAK"
  echo "  Backed up existing _layout.tsx to:"
  echo "    $TABS_BAK"
fi

cat > "$TABS_LAYOUT" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Main bottom tab layout.
 * Exactly 4 tabs, in this order: Portfolio, Items, Add, Search.
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

echo "  ✅ Tabs layout now: Portfolio, Items, Add, Search."
echo

# 3) Fix app entry: send root to /(tabs)/portfolio
if [ -f "$INDEX_FILE" ]; then
  INDEX_BAK="${INDEX_FILE}.bak_fixnav_$(date +%Y%m%d-%H%M%S)"
  cp "$INDEX_FILE" "$INDEX_BAK"
  echo "  Backed up app/index.tsx to:"
  echo "    $INDEX_BAK"
fi

cat > "$INDEX_FILE" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry – always go to the main tab layout (Portfolio tab).
 */
export default function Index() {
  return <Redirect href="/(tabs)/portfolio" />;
}
TSX

echo "  ✅ app/index.tsx now redirects to /(tabs)/portfolio."
echo

# 4) Fix /home/portfolio route: redirect into the Portfolio tab
mkdir -p "$HOME_DIR"

if [ -f "$HOME_PORTFOLIO_FILE" ]; then
  HOME_BAK="${HOME_PORTFOLIO_FILE}.bak_fixnav_$(date +%Y%m%d-%H%M%S)"
  cp "$HOME_PORTFOLIO_FILE" "$HOME_BAK"
  echo "  Backed up existing $HOME_PORTFOLIO_FILE to:"
  echo "    $HOME_BAK"
fi

cat > "$HOME_PORTFOLIO_FILE" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Legacy route: /home/portfolio
 * Redirects into the Portfolio tab in the main tab layout.
 */
export default function HomePortfolioRedirect() {
  return <Redirect href="/(tabs)/portfolio" />;
}
TSX

echo "  ✅ /home/portfolio now redirects to /(tabs)/portfolio."
echo
echo "=== Nav + routes fix complete. Restart Expo to test. ==="
