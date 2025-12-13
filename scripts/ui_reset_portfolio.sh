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

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.ui_reset.$(date +%s)"

cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

const MOCK_WIDGET = {
  collection_value: 12450.0,
  currency: "EUR",
};

const MOCK_TOP_ITEMS = [
  {
    id: "1",
    name: "Demo Charizard",
    category: "pokemon",
    estimated_value: 124.0,
    change_pct: 12.5,
  },
  {
    id: "2",
    name: "Grail Funko Pop",
    category: "funko",
    estimated_value: 45.0,
    change_pct: 3.2,
  },
  {
    id: "3",
    name: "Wave 1 RX-78 (Launch)",
    category: "gunpla",
    estimated_value: 220.0,
    change_pct: -1.8,
  },
];

export default function PortfolioScreen() {
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16, color: "#103b5c" }}>
        Portfolio
      </Text>

      {/* Collection value card */}
      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          marginBottom: 20,
          backgroundColor: "#ffffff",
        }}
      >
        <Text style={{ fontSize: 14, color: "#4a647a" }}>Collection value</Text>
        <Text
          style={{
            fontSize: 28,
            fontWeight: "700",
            marginTop: 4,
            color: "#103b5c",
          }}
        >
          {MOCK_WIDGET.collection_value} {MOCK_WIDGET.currency}
        </Text>
      </View>

      {/* Top items (like a simple list, no summary block) */}
      <Text
        style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}
      >
        Top items
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#ffffff",
        }}
      >
        {MOCK_TOP_ITEMS.map(function (item, idx) {
          const isLast = idx === MOCK_TOP_ITEMS.length - 1;
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
                borderBottomColor: "#f0f3f7",
              }}
            >
              <View>
                <Text style={{ fontWeight: "600", color: "#103b5c" }}>{item.name}</Text>
                <Text style={{ color: "#4a647a", fontSize: 12 }}>
                  {item.category}
                </Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={{ fontWeight: "600", color: "#103b5c" }}>
                  {item.estimated_value} EUR
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

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: data is static but matches what your backend pricing engine returns.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Portfolio UI reset to simple, on-brand layout (no Today summary)."
