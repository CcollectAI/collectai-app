#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_grapharea_$TS"
echo "✅ Backup: $FILE.bak_grapharea_$TS"

cat > "$FILE" <<'TSX'
import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { PortfolioLineChart } from "@/components/PortfolioLineChart";

type RangeKey = "1D" | "7D" | "30D";

const SERIES_30D = [
  { t: "2024-11-01", v: 17250 },
  { t: "2024-11-05", v: 17510 },
  { t: "2024-11-10", v: 18120 },
  { t: "2024-11-15", v: 17980 },
  { t: "2024-11-20", v: 18940 },
  { t: "2024-11-25", v: 19510 },
  { t: "2024-12-06", v: 20121 },
];

const SERIES_7D = [
  { t: "2024-11-30", v: 19410 },
  { t: "2024-12-01", v: 19620 },
  { t: "2024-12-02", v: 19580 },
  { t: "2024-12-03", v: 19840 },
  { t: "2024-12-04", v: 19920 },
  { t: "2024-12-05", v: 20010 },
  { t: "2024-12-06", v: 20121 },
];

const SERIES_1D = [
  { t: "2024-12-06T09:00:00Z", v: 19980 },
  { t: "2024-12-06T11:00:00Z", v: 20040 },
  { t: "2024-12-06T13:00:00Z", v: 20110 },
  { t: "2024-12-06T15:00:00Z", v: 20070 },
  { t: "2024-12-06T17:00:00Z", v: 20121 },
];

const formatEUR0 = (v: number) =>
  new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(v);

export default function PortfolioScreen() {
  const router = useRouter();
  const [range, setRange] = useState<RangeKey>("30D");

  const series = useMemo(() => {
    if (range === "1D") return SERIES_1D;
    if (range === "7D") return SERIES_7D;
    return SERIES_30D;
  }, [range]);

  const latest = series.length ? series[series.length - 1].v : 0;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* TOP HALF = ONE GRAPH AREA */}
        <View style={styles.graphArea}>
          <View style={styles.topRow}>
            <View>
              <Text style={styles.kicker}>Collection Value</Text>
              <Text style={styles.total}>{formatEUR0(latest)}</Text>
            </View>

            {/* Twitch button (notch-safe because inside SafeArea + layout row) */}
            <Pressable
              onPress={() => router.push("/twitch")}
              hitSlop={10}
              style={styles.twitchBtn}
            >
              <Ionicons name="logo-twitch" size={20} color="#0b1f3a" />
            </Pressable>
          </View>

          <View style={styles.rangeRow}>
            {(["1D", "7D", "30D"] as RangeKey[]).map((k) => {
              const active = k === range;
              return (
                <Pressable
                  key={k}
                  onPress={() => setRange(k)}
                  style={[styles.rangePill, active && styles.rangePillActive]}
                >
                  <Text style={[styles.rangeText, active && styles.rangeTextActive]}>
                    {k}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <View style={styles.chartWrap}>
            <PortfolioLineChart
              series={series}
              accentColor="#14b8a6"
              showValueHeader={false}   // removes “strange euro total”
              showAxisLabels={true}     // show min/max + start/end
            />
          </View>
        </View>

        {/* Items/events come later — we are locking the graph area first */}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  content: {
    paddingBottom: 24,
  },

  graphArea: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 8,
  },

  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },

  kicker: {
    fontSize: 12,
    fontWeight: "700",
    color: "#0b1f3a",
    opacity: 0.75,
  },
  total: {
    marginTop: 6,
    fontSize: 34,
    fontWeight: "800",
    color: "#0b1f3a",
    letterSpacing: -0.5,
  },

  twitchBtn: {
    paddingTop: 2,
  },

  rangeRow: {
    marginTop: 10,
    flexDirection: "row",
    gap: 8,
  },
  rangePill: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    backgroundColor: "rgba(11,31,58,0.06)",
  },
  rangePillActive: {
    backgroundColor: "rgba(20,184,166,0.18)",
  },
  rangeText: {
    fontSize: 12,
    fontWeight: "800",
    color: "#0b1f3a",
    opacity: 0.7,
  },
  rangeTextActive: {
    opacity: 1,
  },

  chartWrap: {
    marginTop: 6,
  },
});
TSX

echo "✅ Portfolio top-half graph area updated (EUR + Twitch + flowing layout)."
echo "🛑 SANITY CHECK: npx expo start --tunnel"
