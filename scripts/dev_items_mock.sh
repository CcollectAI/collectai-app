#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.items_mock.$(date +%s)"
else
  echo "Creating new Items screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

const MOCK_ITEMS = [
  {
    id: "1",
    name: "Demo Charizard",
    category: "pokemon",
    predicted_value: 124.0,
    currency: "EUR",
  },
  {
    id: "2",
    name: "Grail Funko Pop",
    category: "funko",
    predicted_value: 45.0,
    currency: "EUR",
  },
  {
    id: "3",
    name: "Wave 1 RX-78 (Launch)",
    category: "gunpla",
    predicted_value: 220.0,
    currency: "EUR",
  },
];

export default function ItemsScreen() {
  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        My Watchlist
      </Text>

      {MOCK_ITEMS.map((item, idx) => (
        <View
          key={item.id}
          style={{
            paddingVertical: 10,
            borderBottomWidth: idx === MOCK_ITEMS.length - 1 ? 0 : 1,
            borderBottomColor: "#eee",
          }}
        >
          <Text style={{ fontWeight: "600" }}>{item.name}</Text>
          <Text>
            {item.category} · {item.predicted_value} {item.currency}
          </Text>
        </View>
      ))}

      <Text style={{ marginTop: 16, color: "#777", fontSize: 12 }}>
        Demo mode: watchlist entries are static examples.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Items screen with mock watchlist."
