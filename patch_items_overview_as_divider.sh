#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

BANNER_FILE="src/components/ItemsOverviewBanner.tsx"

if [ -f "$BANNER_FILE" ]; then
  BAK="${BANNER_FILE}.bak_divider_$(date +%Y%m%d-%H%M%S)"
  cp "$BANNER_FILE" "$BAK"
  echo "📦 Backed up existing ItemsOverviewBanner to:"
  echo "  $BAK"
fi

cat > "$BANNER_FILE" <<'TSX'
import React from "react";
import { View } from "react-native";

/**
 * ItemsOverviewBanner
 *
 * Now behaves as a subtle divider under the Items header / portfolio value.
 * No text, just a Tiffany-style line to visually separate header from the list.
 */
export default function ItemsOverviewBanner() {
  return (
    <View
      style={{
        marginTop: 4,
        marginBottom: 8,
        height: 1,
        backgroundColor: "#D4E4EC", // soft divider line
      }}
    />
  );
}
TSX

echo "✅ ItemsOverviewBanner now renders as a simple divider line (no text)."
