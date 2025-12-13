#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_step2a_linechart_$TS"
echo "✅ Backup created: $FILE.bak_step2a_linechart_$TS"

cat > "$FILE" <<'TSX'
import React from "react";
import { ScrollView, View, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { PortfolioLineChart } from "@/components/PortfolioLineChart";

const SERIES = [
  { t: "2024-12-01", v: 18200 },
  { t: "2024-12-05", v: 18750 },
  { t: "2024-12-10", v: 19120 },
  { t: "2024-12-15", v: 19640 },
  { t: "2024-12-20", v: 20121 },
];

export default function PortfolioScreen() {
  const router = useRouter();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Twitch shortcut */}
      <View style={styles.topRight}>
        <Ionicons
          name="logo-twitch"
          size={20}
          color="#1f2937"
          onPress={() => router.push("/twitch")}
        />
      </View>

      {/* Portfolio value line chart */}
      <View style={styles.chartWrap}>
        <PortfolioLineChart
          series={SERIES}
          accentColor="#14b8a6"
        />
      </View>

      {/* Items + events stay as-is for now */}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f3f4f6", // light gray base
  },
  content: {
    paddingTop: 24,
    paddingBottom: 32,
  },
  topRight: {
    position: "absolute",
    top: 16,
    right: 16,
    zIndex: 10,
  },
  chartWrap: {
    paddingHorizontal: 16,
  },
});
TSX

echo "✅ PortfolioLineChart now active."
echo "🛑 STOP NOW."
echo "➡️ Run: npx expo start --tunnel"
echo "➡️ Expect:"
echo "   - A visible LINE chart"
echo "   - No white card"
echo "   - Integrated background"
