#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$ROOT"

CANDIDATES=("app" "app_full_20251126/app")

echo "=== Normalizing nav + portfolio chart in all known app trees ==="
echo "Candidates:"
printf ' - %s\n' "${CANDIDATES[@]}"
echo

for APPDIR in "${CANDIDATES[@]}"; do
  if [ ! -d "$APPDIR" ]; then
    echo "ℹ️ Skipping $APPDIR (directory does not exist)."
    continue
  fi

  echo "=== Working in app directory: $APPDIR ==="

  # 1) Root app/index.tsx -> always redirect into (tabs)
  ROOT_INDEX="$APPDIR/index.tsx"
  if [ -f "$ROOT_INDEX" ]; then
    BAK_ROOT="${ROOT_INDEX}.bak_rootIndex_$(date +%Y%m%d-%H%M%S)"
    cp "$ROOT_INDEX" "$BAK_ROOT"
    echo "📦 Backed up $ROOT_INDEX -> $BAK_ROOT"
  else
    echo "ℹ️ $ROOT_INDEX did not exist; will create fresh."
  fi

  cat > "$ROOT_INDEX" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry point.
 *
 * Always go straight into the (tabs) group, where the bottom nav
 * (Portfolio / Items / Add / Search) lives.
 */
export default function RootIndex() {
  return <Redirect href="/(tabs)" />;
}
TSX
  echo "✅ Wrote redirect-only root index to $ROOT_INDEX"

  # 2) Bottom tab layout: 4 tabs only
  TABS_LAYOUT="$APPDIR/(tabs)/_layout.tsx"
  if [ -f "$TABS_LAYOUT" ]; then
    BAK_TABS="${TABS_LAYOUT}.bak_navReset_$(date +%Y%m%d-%H%M%S)"
    cp "$TABS_LAYOUT" "$BAK_TABS"
    echo "📦 Backed up $TABS_LAYOUT -> $BAK_TABS"
  else
    echo "ℹ️ $TABS_LAYOUT did not exist; will create fresh."
  fi

  cat > "$TABS_LAYOUT" <<'TSX'
import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Bottom tab layout:
 *
 * Exactly 4 tabs, in this order:
 *  - index        -> "Portfolio"
 *  - items        -> "Items"
 *  - add          -> "Add"
 *  - marketplace  -> "Search"
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
  echo "✅ Wrote 4-tab layout to $TABS_LAYOUT"

  # 3) Wrap (tabs)/portfolio.tsx as a wrapper if it exists
  PORTFOLIO_ROUTE="$APPDIR/(tabs)/portfolio.tsx"
  if [ -f "$PORTFOLIO_ROUTE" ]; then
    BAK_PORT="${PORTFOLIO_ROUTE}.bak_wrapper_$(date +%Y%m%d-%H%M%S)"
    cp "$PORTFOLIO_ROUTE" "$BAK_PORT"
    echo "📦 Backed up $PORTFOLIO_ROUTE -> $BAK_PORT"

    cat > "$PORTFOLIO_ROUTE" <<'TSX'
import React from "react";
import PortfolioScreen from "./index";

/**
 * Wrapper route for /portfolio deep link.
 * Not a separate tab. Uses the same component as (tabs)/index.tsx.
 */
export default function PortfolioRoute() {
  return <PortfolioScreen />;
}
TSX
    echo "✅ Rewrote $PORTFOLIO_ROUTE as wrapper to ./index"
  else
    echo "ℹ️ No $PORTFOLIO_ROUTE found; nothing to wrap."
  fi

  # 4) Tidy SVG chart in (tabs)/index.tsx (if present)
  PORTFOLIO_INDEX="$APPDIR/(tabs)/index.tsx"
  if [ ! -f "$PORTFOLIO_INDEX" ]; then
    echo "ℹ️ No $PORTFOLIO_INDEX found; skipping chart tweak."
  else
    echo "🔧 Checking $PORTFOLIO_INDEX for SVG chart cleanup..."
    python3 <<PYCODE
from pathlib import Path

path = Path(r"$PORTFOLIO_INDEX")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_chartGlobal")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up", path, "->", backup)

changed = False

if "<Svg height={90} width={260}>" in text:
    text = text.replace(
        "<Svg height={90} width={260}>",
        '<Svg height={90} width="100%" viewBox="0 0 260 90" preserveAspectRatio="none">'
    )
    print("✅ Updated fixed-width SVG to responsive in", path)
    changed = True
elif '<Svg height={90} width="100%"' in text and "viewBox" not in text:
    text = text.replace(
        'height={90} width="100%"',
        'height={90} width="100%" viewBox="0 0 260 90" preserveAspectRatio="none"'
    )
    print("✅ Added viewBox/preserveAspectRatio to existing responsive SVG in", path)
    changed = True

if "portfolioChartWrapper" not in text and "<Svg height={90}" in text:
    svg_idx = text.find("<Svg height={90}")
    end_idx = text.find("</Svg>", svg_idx)
    if end_idx != -1:
        end_idx += len("</Svg>")
        block = text[svg_idx:end_idx]
        wrapped = (
            "        <View style={styles.portfolioChartWrapper}>\\n"
            + block.replace("\\n", "\\n        ")
            + "\\n        </View>"
        )
        text = text[:svg_idx] + wrapped + text[end_idx:]
        print("✅ Wrapped SVG in styles.portfolioChartWrapper in", path)
        changed = True

if "portfolioChartWrapper" not in text:
    marker = "const styles = StyleSheet.create({"
    idx = text.find(marker)
    if idx != -1:
        insert_pos = idx + len(marker)
        style_snippet = """
  portfolioChartWrapper: {
    width: "100%",
    marginTop: 8,
    marginBottom: 16,
    alignSelf: "stretch",
  },"""
        text = text[:insert_pos] + style_snippet + text[insert_pos:]
        print("✅ Injected styles.portfolioChartWrapper into StyleSheet in", path)
        changed = True

if changed:
    path.write_text(text, encoding="utf-8")
else:
    print("ℹ️ No SVG chart changes required in", path)
PYCODE
  fi

  echo
done

echo "=== Done applying nav + portfolio tweaks to all candidate app dirs. ==="
