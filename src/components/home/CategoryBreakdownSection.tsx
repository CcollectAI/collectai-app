/**
 * Category breakdown section showing value distribution.
 *
 * Displays horizontal bar chart for top categories and a scrollable
 * row of category cards with item count, value, and percentage.
 * Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { AnimatedPressable } from "@/motion";
import { SkeletonList } from "@/components/Skeleton";
import { radius, text as textToken, fontWeight as fw } from "@/theme/tokens";

// ── Types ──────────────────────────────────────────────────────────────

export type CategoryBreakdownItem = {
  category: string;
  item_count: number;
  total_value: number;
  percentage: number;
};

// ── Props ──────────────────────────────────────────────────────────────

interface CategoryBreakdownSectionProps {
  theme: {
    text: string;
    muted: string;
    card: string;
    border: string;
    accent: string;
    background: string;
  };
  breakdown: CategoryBreakdownItem[];
  loading: boolean;
  formatPrice: (amount: number) => string;
  onCategoryPress?: (categoryName: string) => void;
  resolveCategoryName?: (raw: string) => string;
}

// ── Component ──────────────────────────────────────────────────────────

function CategoryBreakdownSectionInner({
  theme,
  breakdown,
  loading,
  formatPrice,
  onCategoryPress,
  resolveCategoryName,
}: CategoryBreakdownSectionProps) {
  const displayName = (raw: string) => resolveCategoryName?.(raw) ?? raw;
  return (
    <>
      <View style={s.sectionHeader}>
        <Text style={[s.sectionTitle, { color: theme.text }]}>Category Breakdown</Text>
      </View>

      {loading ? (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <SkeletonList count={3} type="row" />
        </View>
      ) : breakdown.length > 0 ? (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          {/* Horizontal bar chart for top 5 */}
          {breakdown.slice(0, 5).map((cat, idx) => {
            const barColors = [
              theme.accent,
              theme.accent + "CC",
              theme.accent + "99",
              theme.accent + "66",
              theme.accent + "44",
            ];
            const barColor = barColors[idx] || theme.accent;
            return (
              <AnimatedPressable
                key={cat.category}
                style={s.breakdownBarRow}
                onPress={() => onCategoryPress?.(cat.category)}
                accessibilityRole="button"
                accessibilityLabel={`${displayName(cat.category)}: ${cat.percentage.toFixed(0)}% of portfolio. Tap to view category.`}
              >
                <Text style={[s.breakdownBarLabel, { color: theme.text }]} numberOfLines={1}>
                  {displayName(cat.category)}
                </Text>
                <View style={s.breakdownBarTrack}>
                  <View
                    style={[
                      s.breakdownBarFill,
                      { backgroundColor: barColor, width: `${Math.max(cat.percentage, 2)}%` as `${number}%` },
                    ]}
                  />
                </View>
                <Text style={[s.breakdownBarPct, { color: theme.muted }]}>
                  {cat.percentage.toFixed(0)}%
                </Text>
              </AnimatedPressable>
            );
          })}

          {/* Scrollable category cards */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={s.breakdownCardsRow}
            style={s.breakdownCardsScroll}
          >
            {breakdown.map((cat) => (
              <AnimatedPressable
                key={cat.category}
                style={[s.breakdownCategoryCard, { backgroundColor: theme.background, borderColor: theme.border }]}
                onPress={() => onCategoryPress?.(cat.category)}
                accessibilityRole="button"
                accessibilityLabel={`${displayName(cat.category)}: ${cat.item_count} item${cat.item_count !== 1 ? "s" : ""}, ${formatPrice(cat.total_value)}, ${cat.percentage.toFixed(0)}%. Tap to view category.`}
              >
                <Text style={[s.breakdownCatName, { color: theme.text }]} numberOfLines={1}>
                  {displayName(cat.category)}
                </Text>
                <Text style={[s.breakdownCatItems, { color: theme.muted }]}>
                  {cat.item_count} item{cat.item_count !== 1 ? "s" : ""}
                </Text>
                <Text style={[s.breakdownCatValue, { color: theme.text }]}>
                  {formatPrice(cat.total_value)}
                </Text>
                <View style={[s.breakdownPctBadge, { backgroundColor: theme.accent + "15" }]}>
                  <Text style={[s.breakdownPctBadgeText, { color: theme.accent }]}>
                    {cat.percentage.toFixed(0)}%
                  </Text>
                </View>
              </AnimatedPressable>
            ))}
          </ScrollView>
        </View>
      ) : (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[s.breakdownEmpty, { color: theme.muted }]}>
            Add items to see your category breakdown.
          </Text>
        </View>
      )}
    </>
  );
}

export const CategoryBreakdownSection = React.memo(CategoryBreakdownSectionInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: textToken.xl,
    fontWeight: fw.extrabold,
  },
  breakdownCard: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 14,
    marginBottom: 20,
  },
  breakdownBarRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  breakdownBarLabel: {
    width: 80,
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
    marginRight: 8,
  },
  breakdownBarTrack: {
    flex: 1,
    height: 10,
    borderRadius: radius.xs,
    backgroundColor: "#E2E8F020",
    overflow: "hidden",
    marginRight: 8,
  },
  breakdownBarFill: {
    height: "100%",
    borderRadius: radius.xs,
  },
  breakdownBarPct: {
    width: 36,
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
    textAlign: "right",
  },
  breakdownCardsScroll: {
    marginTop: 10,
  },
  breakdownCardsRow: {
    gap: 10,
  },
  breakdownCategoryCard: {
    width: 130,
    borderRadius: radius.sm,
    borderWidth: 1,
    padding: 10,
  },
  breakdownCatName: {
    fontSize: textToken.md,
    fontWeight: fw.bold,
    marginBottom: 2,
  },
  breakdownCatItems: {
    fontSize: textToken.sm,
    marginBottom: 4,
  },
  breakdownCatValue: {
    fontSize: textToken.md,
    fontWeight: fw.extrabold,
    marginBottom: 6,
  },
  breakdownPctBadge: {
    alignSelf: "flex-start",
    borderRadius: radius.xs,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  breakdownPctBadgeText: {
    fontSize: textToken.sm,
    fontWeight: fw.bold,
  },
  breakdownEmpty: {
    fontSize: textToken.md,
    textAlign: "center",
    paddingVertical: 16,
  },
});
