#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up existing $TARGET"
  cp "$TARGET" "$TARGET.bak.marketplace_fix.$(date +%s)"
else
  echo "Creating new minimal $TARGET"
  mkdir -p "$(dirname "$TARGET")"
fi

cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

export default function MarketplaceScreen() {
  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingVertical: 32 }}
    >
      <View>
        <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
          Marketplace (Placeholder)
        </Text>
        <Text>
          This is a minimal Marketplace screen used to keep the app stable.
          Backend trust & screenshot intel wiring will be added again once the
          basic navigation is confirmed working.
        </Text>
      </View>
    </ScrollView>
  );
}
EOF

echo "Replaced $TARGET with a minimal, safe Marketplace screen."
