#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

BANNER_FILE="src/components/ItemsOverviewBanner.tsx"

if [ -f "$BANNER_FILE" ]; then
  BAK="${BANNER_FILE}.bak_label_$(date +%Y%m%d-%H%M%S)"
  cp "$BANNER_FILE" "$BAK"
  echo "📦 Backed up existing ItemsOverviewBanner to:"
  echo "  $BAK"
fi

cat > "$BANNER_FILE" <<'TSX'
import React from "react";
import { View, Text } from "react-native";

/**
 * Compact header bubble for the Items screen.
 * Sits directly above the items/portfolio total row to make that section pop.
 */
export default function ItemsOverviewBanner() {
  return (
    <View
      style={{
        marginBottom: 4,
        paddingVertical: 8,
        paddingHorizontal: 12,
        borderRadius: 12,
        backgroundColor: "#E5F4F8",
        borderWidth: 1,
        borderColor: "#B4DDE7",
      }}
    >
      <Text
        style={{
          fontSize: 13,
          fontWeight: "600",
        }}
      >
        Items & portfolio total
      </Text>
    </View>
  );
}
TSX

echo "✅ ItemsOverviewBanner is now a small label bubble without explanation text."
