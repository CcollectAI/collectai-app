#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATE="app/(tabs)/items.tsx"

if [ ! -f "$CANDIDATE" ]; then
  echo "items.tsx not found at app/(tabs)/items.tsx; creating it."
fi

if [ -f "$CANDIDATE" ]; then
  cp "$CANDIDATE" "$CANDIDATE.bak.watchlist.$(date +%s)"
fi

mkdir -p "app/(tabs)"

cat <<'EOF' > "$CANDIDATE"
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function ItemsScreen() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await collectorsApi.fetchWatchlist();
        setItems(res.items ?? []);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        My Watchlist
      </Text>

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
        <Text>No items in your watchlist yet.</Text>
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

echo "Patched app/(tabs)/items.tsx with Watchlist Items screen."
