#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TAB_FILES=("app/(tabs)/index.tsx" "app/(tabs)/items.tsx" "app/(tabs)/add.tsx" "app/(tabs)/marketplace.tsx")

for TARGET in "${TAB_FILES[@]}"; do
  if [ -f "$TARGET" ]; then
    echo "Backing up and resetting $TARGET"
    cp "$TARGET" "$TARGET.bak.minimal.$(date +%s)"
  else
    echo "Creating new minimal tab at $TARGET"
    mkdir -p "$(dirname "$TARGET")"
  fi

  cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

export default function Screen() {
  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingVertical: 32 }}
    >
      <View>
        <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
          Placeholder Screen
        </Text>
        <Text>
          This tab is currently using a minimal placeholder to keep the app stable.
        </Text>
      </View>
    </ScrollView>
  );
}
EOF

done

echo "All tab screens reset to minimal placeholders."
