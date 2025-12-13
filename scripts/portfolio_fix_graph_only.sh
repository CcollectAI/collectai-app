#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_graphfix_$TS"
echo "✅ Backup created: $FILE.bak_graphfix_$TS"

cat > "$FILE" <<'TSX'
import React from "react";
import { SafeAreaView, ScrollView, View, StyleSheet } from "react-native";

import { PortfolioLineChart } from "@/components/PortfolioLineChart";

/**
 * TEMP mock portfolio history
 * Correct shape for PortfolioLineChart
 */
const PORTFOLIO_SERIES = [
  { t: "2024-11-01", v: 17250 },
  { t: "2024-11-08", v: 17680 },
  { t: "2024-11-15", v: 18120 },
  { t: "2024-11-22", v: 18940 },
  { t: "2024-11-29", v: 19510 },
  { t: "2024-12-06", v: 20121 },
];

export default function PortfolioScreen() {
  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Portfolio value line graph */}
        <View style={styles.chartWrap}>
          <PortfolioLineChart
            series={PORTFOLIO_SERIES}
            accentColor="#0ea5e9"
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#f3f4f6", // light gray base
  },
  content: {
    paddingTop: 12,
    paddingBottom: 24,
  },
  chartWrap: {
    paddingHorizontal: 16,
  },
});
TSX

echo "✅ Portfolio graph wired."
echo "🛑 STOP NOW."
echo "➡️ Run: npx expo start --tunnel"
echo "➡️ Expect:"
echo "   - A visible LINE chart"
echo "   - Portfolio value shown"
echo "   - No white card"
echo "   - No notch bleed"
