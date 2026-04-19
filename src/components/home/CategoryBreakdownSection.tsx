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

// Preview data shown when the user's real breakdown is empty — gives a
// concrete sense of what the section will look like once they add items.
// Flagged with `isMock: true` so we can render a "Preview" badge.
const MOCK_BREAKDOWN: CategoryBreakdownItem[] = [
  { category: 'Pokemon',     item_count: 47, total_value: 2340, percentage: 38 },
  { category: 'LEGO',        item_count: 12, total_value: 1680, percentage: 27 },
  { category: 'Hot Toys',    item_count:  8, total_value: 1120, percentage: 18 },
  { category: 'Warhammer',   item_count: 34, total_value:  620, percentage: 10 },
  { category: 'Vinyl Records', item_count: 22, total_value:  440, percentage:  7 },
];

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
  // Fall back to mock preview when user has no items yet (2026-04-19)
  const isPreview = !loading && breakdown.length === 0;
  const effectiveBreakdown = isPreview ? MOCK_BREAKDOWN : breakdown;
  return (
    <>
      <View style={s.sectionHeader}>
        <Text style={[s.sectionTitle, { color: theme.text }]}>Category Breakdown</Text>
        {isPreview && (
          <View style={[s.previewBadge, { backgroundColor: theme.accent + '18' }]}>
            <Text style={[s.previewBadgeText, { color: theme.accent }]}>PREVIEW</Text>
          </View>
        )}
      </View>

      {loading ? (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <SkeletonList count={3} type="row" />
        </View>
      ) : (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          {isPreview && (
            <Text style={[s.previewNote, { color: theme.muted }]}>
              This is how your breakdown will look once you add items.
            </Text>
          )}
          {/* Horizontal bar chart for top 5 */}
          {effectiveBreakdown.slice(0, 5).map((cat, idx) => {
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
                onPress={() => { if (!isPreview) onCategoryPress?.(cat.category); }}
                accessibilityRole="button"
                accessibilityLabel={`${displayName(cat.category)}: ${cat.percentage.toFixed(0)}% of portfolio. Tap to view category.`}
              >
                <Text style={[s.breakdownBarLabel, { color: theme.text }]} numberOfLines={1}>
                  {displayName(cat.category)}
                </Text>
                <View style={[s.breakdownBarTrack, { backgroundColor: theme.border + '20' }]}>
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
            {effectiveBreakdown.map((cat) => (
              <AnimatedPressable
                key={cat.category}
                style={[s.breakdownCategoryCard, { backgroundColor: theme.background, borderColor: theme.border }]}
                onPress={() => { if (!isPreview) onCategoryPress?.(cat.category); }}
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
  previewBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  previewBadgeText: {
    fontSize: 10,
    fontWeight: fw.extrabold,
    letterSpacing: 0.5,
  },
  previewNote: {
    fontSize: 11,
    fontStyle: 'italic',
    marginBottom: 10,
  },
});
