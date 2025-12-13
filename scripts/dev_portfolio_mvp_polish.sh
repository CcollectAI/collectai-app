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
  cp "$TARGET" "$TARGET.bak.portfolio_mvp_polish.$(date +%s)"
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

const MOCK_POSITIONS = [
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
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16 }}>
        Portfolio
      </Text>

      {/* Collection value card */}
      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#ddd",
          marginBottom: 20,
          backgroundColor: "#f5fbff",
        }}
      >
        <Text style={{ fontSize: 14, color: "#555" }}>Collection value</Text>
        <Text
          style={{
            fontSize: 28,
            fontWeight: "700",
            marginTop: 4,
          }}
        >
          {MOCK_WIDGET.collection_value} {MOCK_WIDGET.currency}
        </Text>
        <Text
          style={{
            marginTop: 4,
            color: MOCK_WIDGET.today_change >= 0 ? "#228b22" : "#b00020",
          }}
        >
          Today: {MOCK_WIDGET.today_change} {MOCK_WIDGET.currency} · Biggest
          mover: {MOCK_WIDGET.biggest_mover_name}
        </Text>
      </View>

      {/* Positions list */}
      <Text
        style={{ fontSize: 18, fontWeight: "600", marginBottom: 8 }}
      >
        Top positions
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#eee",
          marginBottom: 20,
          backgroundColor: "#fff",
        }}
      >
        {MOCK_POSITIONS.map((item, idx) => {
          const isLast = idx === MOCK_POSITIONS.length - 1;
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

      {/* Today summary / moat hint */}
      <Text
        style={{ fontSize: 18, fontWeight: "600", marginBottom: 8 }}
      >
        Today&apos;s summary
      </Text>
      <View
        style={{
          padding: 12,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#eee",
          backgroundColor: "#fafafa",
        }}
      >
        <Text style={{ marginBottom: 4 }}>
          • Charizard is your biggest mover today.
        </Text>
        <Text style={{ marginBottom: 4 }}>
          • Gunpla exposure and grails will be used for future risk / trust
          signals.
        </Text>
        <Text style={{ color: "#777", fontSize: 12, marginTop: 4 }}>
          Demo mode: data on this screen is static, but mirrors what the live
          pricing engine already returns on your backend.
        </Text>
      </View>
    </ScrollView>
  );
}
EOF

echo "Replaced Portfolio screen with a richer MVP mock UI."
