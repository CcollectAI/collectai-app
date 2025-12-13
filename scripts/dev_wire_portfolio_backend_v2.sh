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
cp "$TARGET" "$TARGET.bak.backend_v2.$(date +%s)"

cat <<'EOF' > "$TARGET"
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

type Status = "idle" | "loading" | "ok" | "error";

export default function PortfolioScreen() {
  const [widget, setWidget] = useState<any | null>(null);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [insights, setInsights] = useState<any | null>(null);

  const [widgetStatus, setWidgetStatus] = useState<Status>("idle");
  const [watchlistStatus, setWatchlistStatus] = useState<Status>("idle");
  const [insightsStatus, setInsightsStatus] = useState<Status>("idle");

  const [widgetError, setWidgetError] = useState<string | null>(null);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  const [overallLoading, setOverallLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setOverallLoading(true);

      setWidgetStatus("loading");
      setWatchlistStatus("loading");
      setInsightsStatus("loading");

      try {
        const [wRes, wlRes, inxRes] = await Promise.allSettled([
          collectorsApi.fetchHomeWidget(),
          collectorsApi.fetchWatchlist(),
          collectorsApi.fetchInsights(),
        ]);

        if (wRes.status === "fulfilled") {
          setWidget(wRes.value);
          setWidgetStatus("ok");
        } else {
          setWidgetError(wRes.reason?.message ?? String(wRes.reason));
          setWidgetStatus("error");
        }

        if (wlRes.status === "fulfilled") {
          const wl = wlRes.value;
          setWatchlist(wl.items ?? []);
          setWatchlistStatus("ok");
        } else {
          setWatchlistError(wlRes.reason?.message ?? String(wlRes.reason));
          setWatchlistStatus("error");
        }

        if (inxRes.status === "fulfilled") {
          setInsights(inxRes.value);
          setInsightsStatus("ok");
        } else {
          setInsightsError(inxRes.reason?.message ?? String(inxRes.reason));
          setInsightsStatus("error");
        }
      } finally {
        setOverallLoading(false);
      }
    }

    load();
  }, []);

  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 4 }}>
        Portfolio (Backend Debug)
      </Text>
      <Text style={{ marginBottom: 12, color: "#666" }}>
        overallLoading: {String(overallLoading)}
      </Text>

      {/* Widget / home value */}
      <View
        style={{
          marginBottom: 16,
          padding: 12,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#ddd",
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "600" }}>Collection Value</Text>
        <Text style={{ marginTop: 4, color: "#666" }}>
          status: {widgetStatus}
        </Text>
        {widgetStatus === "loading" && <ActivityIndicator />}
        {widgetStatus === "error" && widgetError && (
          <Text style={{ color: "red" }}>{widgetError}</Text>
        )}
        {widgetStatus === "ok" && widget && (
          <>
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
          </>
        )}
      </View>

      {/* Watchlist */}
      <View style={{ marginBottom: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "600" }}>Watchlist</Text>
        <Text style={{ marginTop: 4, color: "#666" }}>
          status: {watchlistStatus}
        </Text>
        {watchlistStatus === "loading" && <ActivityIndicator />}
        {watchlistStatus === "error" && watchlistError && (
          <Text style={{ color: "red" }}>{watchlistError}</Text>
        )}
        {watchlistStatus === "ok" && (
          <>
            <Text style={{ marginTop: 4 }}>
              items: {watchlist.length}
            </Text>
            {watchlist.map((item, idx) => (
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
            ))}
          </>
        )}
      </View>

      {/* Insights */}
      <View style={{ marginBottom: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "600" }}>Risk & Insights</Text>
        <Text style={{ marginTop: 4, color: "#666" }}>
          status: {insightsStatus}
        </Text>
        {insightsStatus === "loading" && <ActivityIndicator />}
        {insightsStatus === "error" && insightsError && (
          <Text style={{ color: "red" }}>{insightsError}</Text>
        )}
        {insightsStatus === "ok" && insights && (
          <>
            {Array.isArray(insights.overexposed_categories) &&
              insights.overexposed_categories.map((cat: any, idx: number) => (
                <Text key={idx}>
                  {cat.category}: {Math.round(cat.share_pct * 100)}% (
                  {cat.risk_level})
                </Text>
              ))}
          </>
        )}
      </View>
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET with backend debug Portfolio screen."
