#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATES=("app/(tabs)/index.tsx" "app/index.tsx")
TARGET=""

for f in "${CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    TARGET="$f"
    break;
  fi
done

if [ -z "$TARGET" ]; then
  echo "No Portfolio screen found; creating app/(tabs)/index.tsx."
  mkdir -p "app/(tabs)"
  TARGET="app/(tabs)/index.tsx"
fi

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.portfolio_manual.$(date +%s)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, ActivityIndicator, Button } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function PortfolioScreen() {
  const [widget, setWidget] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    setWidget(null);
    try {
      const res = await collectorsApi.fetchHomeWidget();
      setWidget(res);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Portfolio
      </Text>
      <Text style={{ marginBottom: 12 }}>
        Tap the button to load your collection value from the backend.
      </Text>

      <Button title="Load Portfolio" onPress={handleLoad} />

      {loading && (
        <View style={{ marginTop: 16 }}>
          <ActivityIndicator />
          <Text style={{ marginTop: 8 }}>Loading portfolio…</Text>
        </View>
      )}

      {error && (
        <Text style={{ marginTop: 16, color: "red" }}>
          Error: {error}
        </Text>
      )}

      {!loading && !error && widget && (
        <View
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#ddd",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600" }}>
            Collection Value
          </Text>
          <Text
            style={{
              fontSize: 22,
              fontWeight: "700",
              marginTop: 4,
            }}
          >
            {widget.collection_value} {widget.currency}
          </Text>
          <Text style={{ marginTop: 4 }}>
            Today: {widget.today_change} {widget.currency} (biggest mover:{" "}
            {widget.biggest_mover_name})
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET with manual Portfolio widget screen."
