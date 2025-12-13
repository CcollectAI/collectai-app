#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.items_mvp_polish.$(date +%s)"
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
    estimated_value: 124.0,
    currency: "EUR",
    change_pct: 12.5,
  },
  {
    id: "2",
    name: "Grail Funko Pop",
    category: "funko",
    estimated_value: 45.0,
    currency: "EUR",
    change_pct: 3.2,
  },
  {
    id: "3",
    name: "Wave 1 RX-78 (Launch)",
    category: "gunpla",
    estimated_value: 220.0,
    currency: "EUR",
    change_pct: -1.8,
  },
];

function computeTotalValue() {
  let total = 0;
  for (let i = 0; i < MOCK_ITEMS.length; i++) {
    total = total + MOCK_ITEMS[i].estimated_value;
  }
  return total;
}

export default function ItemsScreen() {
  const total = computeTotalValue();

  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16 }}>
        Watchlist
      </Text>

      {/* Summary card */}
      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#ddd",
          marginBottom: 16,
          backgroundColor: "#f5fbff",
        }}
      >
        <Text style={{ fontSize: 14, color: "#555" }}>Total watchlist value</Text>
        <Text
          style={{
            fontSize: 24,
            fontWeight: "700",
            marginTop: 4,
          }}
        >
          {total} EUR
        </Text>
        <Text style={{ marginTop: 4, color: "#555" }}>
          These are items you&apos;re tracking closely before buying, selling, or grading.
        </Text>
      </View>

      {/* List of items */}
      <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8 }}>
        Tracked items
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#eee",
          backgroundColor: "#fff",
        }}
      >
        {MOCK_ITEMS.map(function (item, idx) {
          const isLast = idx === MOCK_ITEMS.length - 1;
          const isUp = item.change_pct >= 0;
          return (
            <View
              key={item.id}
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                paddingVertical: 10,
                paddingHorizontal: 12,
                borderBottomWidth: isLast ? 0 : 1,
                borderBottomColor: "#f0f0f0",
              }}
            >
              <View>
                <Text style={{ fontWeight: "600" }}>{item.name}</Text>
                <Text style={{ color: "#666", fontSize: 12 }}>
                  {item.category}
                </Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={{ fontWeight: "600" }}>
                  {item.estimated_value} {item.currency}
                </Text>
                <Text
                  style={{
                    color: isUp ? "#228b22" : "#b00020",
                    fontSize: 12,
                  }}
                >
                  {isUp ? "+" : ""}
                  {item.change_pct}%
                </Text>
              </View>
            </View>
          );
        })}
      </View>

      <Text style={{ marginTop: 16, color: "#777", fontSize: 12 }}>
        Demo mode: these entries mirror how your live watchlist will look once
        wired to the backend watchlist and alert system.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Items screen with polished MVP watchlist UI."
