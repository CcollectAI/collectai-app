#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/items.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.items_manual.$(date +%s)"
else
  echo "Creating new Items screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, ActivityIndicator, Button } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function ItemsScreen() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    setItems([]);
    try {
      const res = await collectorsApi.fetchWatchlist();
      setItems(res.items ?? []);
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
        My Watchlist
      </Text>
      <Text style={{ marginBottom: 12 }}>
        Tap the button to load your watchlist from the backend.
      </Text>

      <Button title="Load Watchlist" onPress={handleLoad} />

      {loading && (
        <View style={{ marginTop: 16 }}>
          <ActivityIndicator />
          <Text style={{ marginTop: 8 }}>Loading watchlist…</Text>
        </View>
      )}

      {error && (
        <Text style={{ marginTop: 16, color: "red" }}>
          Error: {error}
        </Text>
      )}

      {!loading && !error && items.length === 0 && (
        <Text style={{ marginTop: 16 }}>No items loaded yet.</Text>
      )}

      {items.map((item, idx) => (
        <View
          key={item.id ?? idx}
          style={{
            paddingVertical: 8,
            borderBottomWidth: idx === items.length - 1 ? 0 : 1,
            borderBottomColor: "#eee",
          }}
        >
          <Text style={{ fontWeight: "600" }}>
            {item.name ?? "Unnamed item"}
          </Text>
          <Text>
            {item.category ?? "unknown"} ·{" "}
            {item.predicted_value ?? "—"} {item.currency ?? "EUR"}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET with manual Watchlist Items screen."
