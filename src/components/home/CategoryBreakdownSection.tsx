/**
 * Category breakdown section showing value distribution.
 *
 * Displays horizontal bar chart for top categories and a scrollable
 * row of category cards with item count, value, and percentage.
 * Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { SkeletonList } from "@/components/Skeleton";

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
}

// ── Component ──────────────────────────────────────────────────────────

function CategoryBreakdownSectionInner({
  theme,
  breakdown,
  loading,
  formatPrice,
}: CategoryBreakdownSectionProps) {
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
              <View
                key={cat.category}
                style={s.breakdownBarRow}
                accessibilityLabel={`${cat.category}: ${cat.percentage.toFixed(0)}% of portfolio`}
              >
                <Text style={[s.breakdownBarLabel, { color: theme.text }]} numberOfLines={1}>
                  {cat.category}
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
              </View>
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
              <View
                key={cat.category}
                style={[s.breakdownCategoryCard, { backgroundColor: theme.background, borderColor: theme.border }]}
                accessibilityLabel={`${cat.category}: ${cat.item_count} item${cat.item_count !== 1 ? "s" : ""}, ${formatPrice(cat.total_value)}, ${cat.percentage.toFixed(0)}%`}
              >
                <Text style={[s.breakdownCatName, { color: theme.text }]} numberOfLines={1}>
                  {cat.category}
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
              </View>
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
    fontSize: 18,
    fontWeight: "800",
  },
  breakdownCard: {
    borderWidth: 1,
    borderRadius: 12,
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
    fontSize: 12,
    fontWeight: "600",
    marginRight: 8,
  },
  breakdownBarTrack: {
    flex: 1,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#E2E8F020",
    overflow: "hidden",
    marginRight: 8,
  },
  breakdownBarFill: {
    height: "100%",
    borderRadius: 5,
  },
  breakdownBarPct: {
    width: 36,
    fontSize: 12,
    fontWeight: "600",
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
    borderRadius: 10,
    borderWidth: 1,
    padding: 10,
  },
  breakdownCatName: {
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 2,
  },
  breakdownCatItems: {
    fontSize: 11,
    marginBottom: 4,
  },
  breakdownCatValue: {
    fontSize: 14,
    fontWeight: "800",
    marginBottom: 6,
  },
  breakdownPctBadge: {
    alignSelf: "flex-start",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  breakdownPctBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  breakdownEmpty: {
    fontSize: 13,
    textAlign: "center",
    paddingVertical: 16,
  },
});
