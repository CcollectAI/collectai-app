#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.marketplace_mock.$(date +%s)"
else
  echo "Creating new Marketplace screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React from "react";
import { View, Text, ScrollView } from "react-native";

const MOCK_TRUST = {
  seller_id: "demo-user",
  reputation_score: 0.92,
  badge: "Verified Collector",
  risk_flags: ["No chargebacks in last 12 months", "Consistent pricing vs market"],
  authenticity_signals: [
    "High-quality photos with close-ups",
    "Matched serial / print run against known database",
    "Account age > 2 years",
  ],
};

export default function MarketplaceScreen() {
  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Marketplace (Trust Demo)
      </Text>

      <View
        style={{
          padding: 16,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#ddd",
          marginBottom: 16,
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 4 }}>
          Seller: {MOCK_TRUST.seller_id}
        </Text>
        <Text style={{ marginBottom: 4 }}>
          Reputation score: {Math.round(MOCK_TRUST.reputation_score * 100)}%
        </Text>
        <Text style={{ marginBottom: 8 }}>Badge: {MOCK_TRUST.badge}</Text>

        <Text style={{ fontWeight: "600", marginBottom: 4 }}>
          Risk & Behaviour
        </Text>
        {MOCK_TRUST.risk_flags.map((flag, idx) => (
          <Text key={idx}>• {flag}</Text>
        ))}

        <Text style={{ fontWeight: "600", marginTop: 8, marginBottom: 4 }}>
          Authenticity Signals
        </Text>
        {MOCK_TRUST.authenticity_signals.map((sig, idx) => (
          <Text key={idx}>• {sig}</Text>
        ))}
      </View>

      <Text style={{ color: "#777", fontSize: 12 }}>
        Demo mode: this shows how in-app trust and anti-fraud analysis will look
        once wired to your models.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Replaced Marketplace screen with mock trust / anti-fraud demo."
