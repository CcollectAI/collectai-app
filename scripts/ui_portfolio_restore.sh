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
cp "$TARGET" "$TARGET.bak.ui_portfolio_restore.$(date +%s)"

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

// Simple static "graph" bars to bring back the Robinhood-ish feel
const MOCK_HISTORY = [11800, 12120, 12050, 12200, 12340, 12400, 12450];

function formatCurrency(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export default function PortfolioScreen() {
  const maxValue = MOCK_HISTORY.reduce(function (acc, v) {
    return v > acc ? v : acc;
  }, 0);

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
          marginBottom: 16,
          backgroundColor: "#ffffff",
        }}
      >
        <Text style={{ fontSize: 14, color: "#4a647a" }}>Collection value</Text>
        <Text
          style={{
            fontSize: 30,
            fontWeight: "700",
            marginTop: 4,
            color: "#103b5c",
          }}
        >
          {formatCurrency(MOCK_WIDGET.collection_value)} {MOCK_WIDGET.currency}
        </Text>
      </View>

      {/* Simple inline "graph" – no backend, just static bars */}
      <View
        style={{
          padding: 12,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          marginBottom: 20,
          backgroundColor: "#ffffff",
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: "600",
            marginBottom: 8,
            color: "#103b5c",
          }}
        >
          Value (last 7 points – demo)
        </Text>
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-end",
            height: 80,
          }}
        >
          {MOCK_HISTORY.map(function (v, idx) {
            const h = maxValue > 0 ? (v / maxValue) * 70 : 0;
            return (
              <View
                key={idx}
                style={{
                  width: 14,
                  marginRight: idx === MOCK_HISTORY.length - 1 ? 0 : 6,
                  height: h,
                  backgroundColor: "#1fb6ff",
                  borderRadius: 4,
                }}
              />
            );
          })}
        </View>
      </View>

      {/* Top items */}
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
        Demo mode: graph and values are static examples. Live version will use your pricing API.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Portfolio tab restored with graph-style section and formatted numbers."
