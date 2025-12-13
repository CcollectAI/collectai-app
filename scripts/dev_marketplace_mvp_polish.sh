#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.marketplace_mvp_polish.$(date +%s)"
else
  echo "Creating new Marketplace screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Button } from "react-native";

const MOCK_TRUST = {
  seller_id: "demo-user",
  reputation_score: 0.92,
  badge: "Verified Collector",
  risk_flags: [
    "No chargebacks in last 12 months",
    "Consistent pricing vs market comps",
    "Low dispute rate across 50+ sales",
  ],
  authenticity_signals: [
    "High-quality macro photos (edges, holo, corners)",
    "Serial / print run matches known database",
    "Previous trades for similar grails completed successfully",
  ],
};

const MOCK_AUTH_SCAN = {
  item_name: "Demo Charizard Grail",
  authenticity_score: 0.88,
  risk_notes: [
    "Edges and surface look consistent with genuine print.",
    "Holo pattern matches reference set.",
    "Slight wear on back edges – consistent with stated condition.",
  ],
  suggested_action: "Safe to pursue – negotiate around minor wear.",
};

export default function MarketplaceScreen() {
  const [scanShown, setScanShown] = useState(false);

  const handleSimulateScan = () => {
    setScanShown(true);
  };

  const repPercent = Math.round(MOCK_TRUST.reputation_score * 100);
  const authPercent = Math.round(MOCK_AUTH_SCAN.authenticity_score * 100);

  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16 }}>
        Marketplace
      </Text>

      {/* Seller trust card */}
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
        <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4 }}>
          Seller trust overview
        </Text>
        <Text style={{ marginBottom: 4 }}>
          Seller: {MOCK_TRUST.seller_id}
        </Text>
        <Text style={{ marginBottom: 4 }}>
          Reputation score: {repPercent}%
        </Text>
        <Text style={{ marginBottom: 8 }}>Badge: {MOCK_TRUST.badge}</Text>

        <Text style={{ fontWeight: "600", marginBottom: 4 }}>
          Behaviour & risk
        </Text>
        {MOCK_TRUST.risk_flags.map(function (flag, idx) {
          return (
            <Text key={idx} style={{ fontSize: 13 }}>
              • {flag}
            </Text>
          );
        })}

        <Text
          style={{ fontWeight: "600", marginTop: 8, marginBottom: 4 }}
        >
          Authenticity signals
        </Text>
        {MOCK_TRUST.authenticity_signals.map(function (sig, idx) {
          return (
            <Text key={idx} style={{ fontSize: 13 }}>
              • {sig}
            </Text>
          );
        })}
      </View>

      {/* Authenticity scanner demo */}
      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#eee",
          marginBottom: 16,
          backgroundColor: "#fff",
        }}
      >
        <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 8 }}>
          Authenticity checker (demo)
        </Text>
        <Text style={{ marginBottom: 8, color: "#555" }}>
          In the full version, you&apos;ll scan a photo or screenshot and the app
          will run anti-fraud checks against your models and marketplaces.
        </Text>

        <Button title="Simulate authenticity scan" onPress={handleSimulateScan} />

        {scanShown && (
          <View style={{ marginTop: 12 }}>
            <Text style={{ fontWeight: "600", marginBottom: 4 }}>
              Result: {MOCK_AUTH_SCAN.item_name}
            </Text>
            <Text style={{ marginBottom: 4 }}>
              Authenticity score: {authPercent}%
            </Text>
            <Text style={{ fontWeight: "600", marginTop: 4 }}>
              Notes
            </Text>
            {MOCK_AUTH_SCAN.risk_notes.map(function (note, idx) {
              return (
                <Text key={idx} style={{ fontSize: 13 }}>
                  • {note}
                </Text>
              );
            })}
            <Text style={{ marginTop: 8 }}>
              Suggested action: {MOCK_AUTH_SCAN.suggested_action}
            </Text>
          </View>
        )}
      </View>

      <Text style={{ color: "#777", fontSize: 12 }}>
        Demo mode: this screen shows how your trust & authenticity moat will be
        surfaced in the UI. All values are static examples, not live model
        output.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Marketplace screen with polished MVP trust + authenticity UI."
