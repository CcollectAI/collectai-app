/**
 * Trending categories list for the marketplace screen.
 *
 * Renders a ranked list of trending categories, each row
 * showing a numbered rank badge, category name, and trend
 * metadata (e.g. "+12% this month").
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";

// ── Exported types ──────────────────────────────────────────────────────

export type TrendingCategory = {
  id: string;
  name: string;
  meta: string;
};

// ── Props ───────────────────────────────────────────────────────────────

interface TrendingCategoriesGridProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
  };
  categories: TrendingCategory[];
  onCategoryPress: (categoryId: string) => void;
}

// ── Component ───────────────────────────────────────────────────────────

function TrendingCategoriesGridInner({
  theme,
  categories,
  onCategoryPress,
}: TrendingCategoriesGridProps) {
  return (
    <View style={s.section}>
      <Text style={[s.sectionTitle, { color: theme.text }]}>
        Trending categories
      </Text>
      <View style={s.trendingList}>
        {categories.map((cat, index) => (
          <AnimatedPressable
            key={cat.id}
            style={[s.trendingRow, { borderColor: theme.border }]}
            onPress={() => onCategoryPress(cat.id)}
            accessibilityRole="button"
            accessibilityLabel={`${cat.name}, ${cat.meta}`}
          >
            <View style={[s.trendingRank, { backgroundColor: theme.accent + "20" }]}>
              <Text style={[s.trendingRankText, { color: theme.accent }]}>
                {index + 1}
              </Text>
            </View>
            <View style={s.trendingInfo}>
              <Text style={[s.trendingName, { color: theme.text }]}>{cat.name}</Text>
              <Text style={[s.trendingMeta, { color: theme.muted }]}>{cat.meta}</Text>
            </View>
            <Ionicons name="trending-up" size={18} color={theme.accent} />
          </AnimatedPressable>
        ))}
      </View>
    </View>
  );
}

export const TrendingCategoriesGrid = React.memo(TrendingCategoriesGridInner);

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  section: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 6,
  },
  trendingList: {
    gap: 8,
  },
  trendingRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  trendingRank: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  trendingRankText: {
    fontSize: 14,
    fontWeight: "700",
  },
  trendingInfo: {
    flex: 1,
  },
  trendingName: {
    fontSize: 14,
    fontWeight: "600",
  },
  trendingMeta: {
    fontSize: 11,
    marginTop: 2,
  },
});
