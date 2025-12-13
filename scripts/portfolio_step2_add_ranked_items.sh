#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_step2_items_$TS"
echo "✅ Backup created: $FILE.bak_step2_items_$TS"

cat > "$FILE" <<'TSX'
import React from "react";
import { View, ScrollView, Text, StyleSheet } from "react-native";
import { useRouter } from "expo-router";

import PortfolioChartRobinhood from "@/components/PortfolioChartRobinhood";

type Item = {
  id: string;
  name: string;
  category: string;
  value: number;
};

// TEMP mock data — visual only
const ITEMS: Item[] = [
  { id: "1", name: "Charizard GX", category: "Pokémon", value: 9900 },
  { id: "2", name: "Pikachu Illustrator", category: "Pokémon", value: 8200 },
  { id: "3", name: "Blastoise Base", category: "Pokémon", value: 5100 },
  { id: "4", name: "Mewtwo Promo", category: "Pokémon", value: 3400 },
  { id: "5", name: "Umbreon Alt Art", category: "Pokémon", value: 2100 },
  { id: "6", name: "LEGO UCS Falcon", category: "LEGO", value: 7800 },
  { id: "7", name: "LEGO UCS X-Wing", category: "LEGO", value: 6200 },
  { id: "8", name: "LEGO Taj Mahal", category: "LEGO", value: 4400 },
  { id: "9", name: "LEGO Colosseum", category: "LEGO", value: 3900 },
  { id: "10", name: "LEGO Batmobile", category: "LEGO", value: 3100 },
];

const formatUSD = (v: number) =>
  `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

export default function PortfolioScreen() {
  const router = useRouter();

  const series = [
    { t: "Mon", v: 18200 },
    { t: "Tue", v: 18850 },
    { t: "Wed", v: 19120 },
    { t: "Thu", v: 19800 },
    { t: "Fri", v: 20121 },
  ];

  const grouped = ITEMS.reduce<Record<string, Item[]>>((acc, item) => {
    acc[item.category] = acc[item.category] || [];
    acc[item.category].push(item);
    return acc;
  }, {});

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Chart */}
      <View style={styles.chartWrap}>
        <PortfolioChartRobinhood series={series} currency="USD" />
      </View>

      {/* Ranked items by category */}
      <View style={styles.itemsWrap}>
        {Object.entries(grouped).map(([category, items]) => {
          const topFive = [...items]
            .sort((a, b) => b.value - a.value)
            .slice(0, 5);

          return (
            <View key={category} style={styles.categoryBlock}>
              <Text style={styles.categoryTitle}>{category}</Text>

              {topFive.map((item) => (
                <View key={item.id} style={styles.itemRow}>
                  <Text style={styles.itemName}>{item.name}</Text>
                  <Text style={styles.itemValue}>
                    {formatUSD(item.value)}
                  </Text>
                </View>
              ))}
            </View>
          );
        })}
      </View>

      {/* STEP 3 will add Twitch icon */}
      {/* STEP 4 will add upcoming events */}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#E7FBFF",
  },
  content: {
    paddingTop: 16,
    paddingBottom: 32,
  },
  chartWrap: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  itemsWrap: {
    paddingHorizontal: 16,
  },
  categoryBlock: {
    marginBottom: 24,
  },
  categoryTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0B1F3A",
    marginBottom: 8,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(11,31,58,0.08)",
  },
  itemName: {
    fontSize: 14,
    color: "#0B1F3A",
  },
  itemValue: {
    fontSize: 14,
    fontWeight: "600",
    color: "#0B1F3A",
  },
});
TSX

echo "✅ Ranked items list added."
echo "🛑 STOP NOW."
echo "➡️  Run: npx expo start --tunnel"
echo "➡️  Sanity check:"
echo "    - Chart still visible"
echo "    - Categories render"
echo "    - Top 5 items per category"
echo "    - Values like $20,121"
