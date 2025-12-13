#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.ui_reset.$(date +%s)"
else
  echo "Creating new Items screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Button } from "react-native";

const MOCK_CATEGORIES = [
  { id: "pokemon", label: "Pokémon" },
  { id: "funko", label: "Funko Pops" },
  { id: "gunpla", label: "Gunpla & model kits" },
  { id: "mtg", label: "Magic: The Gathering" },
  { id: "designer-toys", label: "Designer / Art Toys" },
];

const MOCK_WATCHLIST = [
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
];

export default function ItemsScreen() {
  const [showWatchlist, setShowWatchlist] = useState(false);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16, color: "#103b5c" }}>
        Items
      </Text>

      {/* Categories */}
      <Text
        style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}
      >
        Categories
      </Text>
      <View
        style={{
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#ffffff",
          marginBottom: 16,
        }}
      >
        {MOCK_CATEGORIES.map(function (cat, idx) {
          const isLast = idx === MOCK_CATEGORIES.length - 1;
          return (
            <View
              key={cat.id}
              style={{
                paddingVertical: 10,
                paddingHorizontal: 12,
                borderBottomWidth: isLast ? 0 : 1,
                borderBottomColor: "#f0f3f7",
              }}
            >
              <Text style={{ color: "#103b5c", fontWeight: "500" }}>
                {cat.label}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Watchlist toggle */}
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
        Watchlist
      </Text>
      <Text style={{ marginBottom: 8, color: "#4a647a" }}>
        These are items you&apos;re tracking closely. In the full app this will be a separate screen reachable from item detail and alerts.
      </Text>
      <Button
        title={showWatchlist ? "Hide watchlist" : "Show watchlist"}
        onPress={function () {
          setShowWatchlist(!showWatchlist);
        }}
      />

      {showWatchlist && (
        <View
          style={{
            marginTop: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          {MOCK_WATCHLIST.map(function (item, idx) {
            const isLast = idx === MOCK_WATCHLIST.length - 1;
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
                  <Text style={{ fontWeight: "600", color: "#103b5c" }}>
                    {item.name}
                  </Text>
                  <Text style={{ color: "#4a647a", fontSize: 12 }}>
                    {item.category}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={{ fontWeight: "600", color: "#103b5c" }}>
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
      )}

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: categories and watchlist are static. Later, watchlist will be a dedicated screen and tied to alerts.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Items UI reset: categories first, watchlist behind a button."
