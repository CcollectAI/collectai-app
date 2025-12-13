#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/add.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.ui_add_quickscan_mvp.$(date +%s)"
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

  const handleSimulate = function () {
    setShown(true);
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 12, color: "#103b5c" }}>
        Add / QuickScan
      </Text>
      <Text style={{ marginBottom: 16, color: "#4a647a" }}>
        MVP flow: you&apos;ll open the camera or upload a photo. For now, tap below to simulate a QuickScan result.
      </Text>

      <Button title="Simulate QuickScan" onPress={handleSimulate} />

      {shown && (
        <View
          style={{
            marginTop: 16,
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            {MOCK_QUICKSCAN.prediction.name}
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Category: {MOCK_QUICKSCAN.attributes.category}
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Edition: {MOCK_QUICKSCAN.attributes.edition_guess}
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Condition: {MOCK_QUICKSCAN.attributes.condition_guess}
          </Text>
          <Text style={{ marginTop: 8, color: "#103b5c" }}>
            Estimated range: {MOCK_QUICKSCAN.prediction.estimated_low} -{" "}
            {MOCK_QUICKSCAN.prediction.estimated_high}{" "}
            {MOCK_QUICKSCAN.prediction.currency}
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Confidence: {Math.round(MOCK_QUICKSCAN.prediction.confidence * 100)}%
          </Text>
        </View>
      )}

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: this mirrors the QuickScan output you already have on the backend (q10 / q50 / q90 pricing and attributes).
      </Text>
    </ScrollView>
  );
}
EOF

echo "Add tab restored as QuickScan MVP screen."
