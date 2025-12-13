#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_step1_5_chartdata_$TS"
echo "✅ Backup created: $FILE.bak_step1_5_chartdata_$TS"

cat > "$FILE" <<'TSX'
import React from "react";
import {
  View,
  ScrollView,
  Text,
  StyleSheet,
  Pressable,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import PortfolioChartRobinhood from "@/components/PortfolioChartRobinhood";

/**
 * IMPORTANT:
 * PortfolioChartRobinhood expects:
 * {
 *   points: { x: number; y: number }[]
 * }
 * NOT arbitrary objects.
 */

const PORTFOLIO_SERIES = {
  points: [
    { x: 1, y: 17850 },
    { x: 2, y: 18200 },
    { x: 3, y: 18740 },
    { x: 4, y: 19110 },
    { x: 5, y: 19890 },
    { x: 6, y: 20121 },
  ],
};

export default function PortfolioScreen() {
  const router = useRouter();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Twitch icon (unchanged positioning for now) */}
      <View style={styles.topRight}>
        <Pressable onPress={() => router.push("/twitch")} hitSlop={10}>
          <Ionicons name="logo-twitch" size={22} color="#6441A5" />
        </Pressable>
      </View>

      {/* Portfolio Value Line Graph */}
      <View style={styles.chartWrap}>
        <PortfolioChartRobinhood
          points={PORTFOLIO_SERIES.points}
          currency="USD"
          showCurrentValue
        />
      </View>

      {/* Items + events untouched in this step */}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#E7FBFF",
  },
  content: {
    paddingTop: 24,
    paddingBottom: 32,
  },
  topRight: {
    position: "absolute",
    top: 12,
    right: 16,
    zIndex: 10,
  },
  chartWrap: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
});
TSX

echo "✅ Chart data fixed."
echo "🛑 STOP NOW."
echo "➡️  Run: npx expo start --tunnel"
echo "➡️  EXPECTATION:"
echo "    - A visible portfolio value line graph"
echo "    - Value trend over time"
echo "    - NO white empty box"
