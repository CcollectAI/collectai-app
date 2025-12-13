#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATES=("app/(tabs)/index.tsx" "app/index.tsx")
TARGET=""

for f in "${CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    TARGET="$f"
    break
  fi
done

if [ -z "$TARGET" ]; then
  echo "No Portfolio screen found; creating app/(tabs)/index.tsx."
  mkdir -p "app/(tabs)"
  TARGET="app/(tabs)/index.tsx"
fi

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.portfolio_mock.$(date +%s)"
fi

cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

const MOCK_WIDGET = {
  collection_value: 12450.0,
  today_change: 145.0,
  biggest_mover_name: "Demo Charizard",
  biggest_mover_change: 12.5,
  currency: "EUR",
};

export default function PortfolioScreen() {
  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Portfolio
      </Text>

      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#ddd",
          marginBottom: 16,
        }}
      >
        <Text style={{ fontSize: 16, fontWeight: "600" }}>Collection Value</Text>
        <Text
          style={{
            fontSize: 26,
            fontWeight: "700",
            marginTop: 4,
          }}
        >
          {MOCK_WIDGET.collection_value} {MOCK_WIDGET.currency}
        </Text>
        <Text style={{ marginTop: 4 }}>
          Today: {MOCK_WIDGET.today_change} {MOCK_WIDGET.currency} (biggest
          mover: {MOCK_WIDGET.biggest_mover_name},{" "}
          {MOCK_WIDGET.biggest_mover_change}%)
        </Text>
      </View>

      <Text style={{ color: "#777", fontSize: 12 }}>
        Demo mode: values shown here are static sample data, not live API
        responses.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Portfolio screen with mock collection widget."
