#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATES=("app/(tabs)/index.tsx" "app/index.tsx")
TARGET=""

for f in "${CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    TARGET="$f"
    break
  fi
done

if [ -z "$TARGET" ]; then
  echo "No portfolio screen found at app/(tabs)/index.tsx or app/index.tsx; nothing changed."
  exit 0
fi

echo "Patching $TARGET (backup will be created)."
cp "$TARGET" "$TARGET.bak.backend.$(date +%s)"

cat <<'EOF' > "$TARGET"
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function PortfolioScreen() {
  const [widget, setWidget] = useState<any | null>(null);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [insights, setInsights] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [w, wl, inx] = await Promise.all([
          collectorsApi.fetchHomeWidget(),
          collectorsApi.fetchWatchlist(),
          collectorsApi.fetchInsights(),
        ]);
        setWidget(w);
        setWatchlist(wl.items ?? []);
        setInsights(inx);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
        <Text style={{ marginTop: 8 }}>Loading portfolio…</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Portfolio (Live Backend)
      </Text>

      {error && (
        <Text style={{ color: "red", marginBottom: 12 }}>
          Error: {error}
        </Text>
      )}

      {widget && (
        <View
          style={{
            marginBottom: 16,
            padding: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#ddd",
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600" }}>
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

      <View style={{ marginBottom: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8 }}>
          Watchlist ({watchlist.length})
        </Text>
        {watchlist.length === 0 ? (
          <Text>No items in watchlist yet.</Text>
        ) : (
          watchlist.map((item, idx) => (
            <View
              key={item.id ?? idx}
              style={{
                paddingVertical: 8,
                borderBottomWidth: idx === watchlist.length - 1 ? 0 : 1,
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
          ))
        )}
      </View>

      {insights && (
        <View style={{ marginTop: 8 }}>
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 4 }}>
            Risk & Insights
          </Text>
          {Array.isArray(insights.overexposed_categories) &&
            insights.overexposed_categories.map((cat: any, idx: number) => (
              <Text key={idx}>
                {cat.category}: {Math.round(cat.share_pct * 100)}% (
                {cat.risk_level})
              </Text>
            ))}
        </View>
      )}
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET to show live backend data on the Portfolio screen."
