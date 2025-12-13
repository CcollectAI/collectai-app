#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATES=("app/(tabs)/add.tsx" "app/add.tsx")
TARGET=""

for f in "${CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    TARGET="$f"
    break
  fi
done

if [ -z "$TARGET" ]; then
  echo "No Add screen found; creating app/(tabs)/add.tsx."
  mkdir -p "app/(tabs)"
  TARGET="app/(tabs)/add.tsx"
fi

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.add_manual.$(date +%s)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, ActivityIndicator, Button } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function AddScreen() {
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleQuickScan = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await collectorsApi.quickscanSingle();
      setResult(res);
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
        Add Item (QuickScan)
      </Text>
      <Text style={{ marginBottom: 12 }}>
        Tap the button below to call the backend QuickScan demo endpoint.
      </Text>

      <Button title="Run QuickScan (demo)" onPress={handleQuickScan} />

      {loading && (
        <View style={{ marginTop: 16 }}>
          <ActivityIndicator />
          <Text style={{ marginTop: 8 }}>Scanning…</Text>
        </View>
      )}

      {error && (
        <Text style={{ marginTop: 16, color: "red" }}>
          Error: {error}
        </Text>
      )}

      {result && (
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
            QuickScan Result
          </Text>
          <Text selectable style={{ fontFamily: "monospace" }}>
            {JSON.stringify(result, null, 2)}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET with manual QuickScan Add screen."
