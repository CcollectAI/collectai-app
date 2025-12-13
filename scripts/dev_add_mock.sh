#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/add.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.add_mock.$(date +%s)"
else
  echo "Creating new Add screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Button } from "react-native";

const MOCK_QUICKSCAN = {
  item_id: null,
  attributes: {
    category: "mtg",
    edition_guess: "Unlimited",
    condition_guess: "Near Mint",
    rarity_score: 0.82,
  },
  prediction: {
    name: "Demo Black Lotus",
    estimated_low: 18000.0,
    estimated_mid: 22000.0,
    estimated_high: 26000.0,
    currency: "EUR",
    confidence: 0.91,
  },
};

export default function AddScreen() {
  const [shown, setShown] = useState(false);

  const handleSimulate = () => {
    setShown(true);
  };

  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Add Item (QuickScan Demo)
      </Text>
      <Text style={{ marginBottom: 16 }}>
        This simulates a QuickScan result using static data (no network).
      </Text>

      <Button title="Simulate QuickScan" onPress={handleSimulate} />

      {shown && (
        <View
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#ddd",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 4 }}>
            Result: {MOCK_QUICKSCAN.prediction.name}
          </Text>
          <Text>
            Category: {MOCK_QUICKSCAN.attributes.category} · Edition:{" "}
            {MOCK_QUICKSCAN.attributes.edition_guess}
          </Text>
          <Text>Condition: {MOCK_QUICKSCAN.attributes.condition_guess}</Text>
          <Text style={{ marginTop: 8 }}>
            Estimated range: {MOCK_QUICKSCAN.prediction.estimated_low} -{" "}
            {MOCK_QUICKSCAN.prediction.estimated_high}{" "}
            {MOCK_QUICKSCAN.prediction.currency}
          </Text>
          <Text>
            Confidence:{" "}
            {Math.round(MOCK_QUICKSCAN.prediction.confidence * 100)}%
          </Text>
        </View>
      )}

      <Text style={{ marginTop: 16, color: "#777", fontSize: 12 }}>
        Demo mode: this represents how a future AI QuickScan will behave.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Add screen with mock QuickScan demo."
