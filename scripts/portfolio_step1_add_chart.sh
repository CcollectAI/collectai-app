#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_step1_chart_$TS"
echo "✅ Backup created: $FILE.bak_step1_chart_$TS"

cat > "$FILE" <<'TSX'
import React from "react";
import { View, ScrollView, StyleSheet } from "react-native";
import { useRouter } from "expo-router";

// CHART (existing component in repo)
import PortfolioChartRobinhood from "@/components/PortfolioChartRobinhood";

export default function PortfolioScreen() {
  const router = useRouter();

  // TEMP mock data — visual only, no backend
  const series = [
    { t: "Mon", v: 18200 },
    { t: "Tue", v: 18850 },
    { t: "Wed", v: 19120 },
    { t: "Thu", v: 19800 },
    { t: "Fri", v: 20121 },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Portfolio Chart */}
      <View style={styles.chartWrap}>
        <PortfolioChartRobinhood
          series={series}
          currency="USD"
        />
      </View>

      {/* STEP 2 will insert items list here */}
      {/* STEP 3 will insert Twitch icon */}
      {/* STEP 4 will insert events */}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#E7FBFF", // unified background
  },
  content: {
    paddingTop: 16,
    paddingBottom: 32,
  },
  chartWrap: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
});
TSX

echo "✅ Portfolio chart injected."
echo "🛑 STOP NOW."
echo "➡️  Run: npx expo start --tunnel"
echo "➡️  Sanity check: chart visible at top, app loads, no crash."
