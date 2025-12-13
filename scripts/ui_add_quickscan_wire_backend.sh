#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/add.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Add screen not found at $TARGET, creating it."
  mkdir -p "app/(tabs)"
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.quickscan_wire.$(date +%s)"

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Button } from "react-native";
import { API_BASE } from "../../src/api/config";

type QuickscanResponse = {
  item_id?: string | null;
  attributes?: {
    category?: string;
    edition_guess?: string;
    condition_guess?: string;
    rarity_score?: number;
  };
  prediction?: {
    name?: string;
    estimated_low?: number;
    estimated_mid?: number;
    estimated_high?: number;
    currency?: string;
    confidence?: number;
  };
};

export default function AddScreen() {
  const [status, setStatus] = useState<string | null>(null);
  const [parsed, setParsed] = useState<QuickscanResponse | null>(null);
  const [rawBody, setRawBody] = useState<string | null>(null);

  const handleQuickscan = async function () {
    setStatus("Loading...");
    setParsed(null);
    setRawBody(null);

    try {
      const url = API_BASE + "/quickscan-advanced/single";
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: "{}",
      });

      const text = await res.text();
      setRawBody(text);

      let json: QuickscanResponse | null = null;
      try {
        json = JSON.parse(text);
      } catch (e) {
        json = null;
      }

      setParsed(json);
      setStatus("Done (status=" + res.status + ", ok=" + String(res.ok) + ")");
    } catch (e: any) {
      setStatus("Error while calling QuickScan");
      setParsed(null);
      setRawBody(String(e && e.message ? e.message : e));
    }
  };

  const pred = parsed && parsed.prediction ? parsed.prediction : null;
  const attrs = parsed && parsed.attributes ? parsed.attributes : null;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 12, color: "#103b5c" }}>
        Add / QuickScan
      </Text>

      <Text style={{ marginBottom: 16, color: "#4a647a" }}>
        MVP: tap the button to call the backend QuickScan endpoint and see a demo
        prediction (category, edition, condition, rarity and price range).
      </Text>

      <Button title="Run QuickScan demo" onPress={handleQuickscan} />

      {status && (
        <Text style={{ marginTop: 12, color: "#4a647a", fontSize: 12 }}>
          Status: {status}
        </Text>
      )}

      {pred && (
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
            {pred.name || "QuickScan result"}
          </Text>
          {attrs && (
            <>
              {attrs.category && (
                <Text style={{ color: "#4a647a" }}>Category: {attrs.category}</Text>
              )}
              {attrs.edition_guess && (
                <Text style={{ color: "#4a647a" }}>Edition: {attrs.edition_guess}</Text>
              )}
              {attrs.condition_guess && (
                <Text style={{ color: "#4a647a" }}>Condition: {attrs.condition_guess}</Text>
              )}
              {typeof attrs.rarity_score === "number" && (
                <Text style={{ color: "#4a647a" }}>
                  Rarity score: {Math.round(attrs.rarity_score * 100)} / 100
                </Text>
              )}
            </>
          )}
          <Text style={{ marginTop: 8, color: "#103b5c" }}>
            Estimated range: {pred.estimated_low} – {pred.estimated_high}{" "}
            {pred.currency || "EUR"}
          </Text>
          {typeof pred.estimated_mid === "number" && (
            <Text style={{ color: "#4a647a" }}>
              Mid: {pred.estimated_mid} {pred.currency || "EUR"}
            </Text>
          )}
          {typeof pred.confidence === "number" && (
            <Text style={{ color: "#4a647a" }}>
              Confidence: {Math.round(pred.confidence * 100)}%
            </Text>
          )}
        </View>
      )}

      {rawBody && (
        <View
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#f8fcff",
          }}
        >
          <Text
            style={{
              fontFamily: "monospace",
              fontSize: 11,
              color: "#103b5c",
            }}
          >
            {rawBody}
          </Text>
        </View>
      )}

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: backend uses a stub dataset, but this is the same API surface you will
        use later for real model predictions and logging into the portfolio or marketplace.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Add tab now wired to backend /quickscan-advanced/single."
