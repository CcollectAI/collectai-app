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
  /** Opens the whole collection, unfiltered. Omit to hide the action. */
  onAllItemsPress?: () => void;
  resolveCategoryName?: (raw: string) => string;
}

// ── Component ──────────────────────────────────────────────────────────

function CategoryBreakdownSectionInner({
  theme,
  breakdown,
  loading,
  formatPrice,
  onCategoryPress,
  onAllItemsPress,
  resolveCategoryName,
}: CategoryBreakdownSectionProps) {
  const displayName = (raw: string) => resolveCategoryName?.(raw) ?? raw;
  const isEmpty = !loading && breakdown.length === 0;
  return (
    <>
      <View style={s.sectionHeader}>
        <Text style={[s.sectionTitle, { color: theme.text }]}>Category Breakdown</Text>
        {/* "All items" — the ONLY unfiltered route into the collection list.
            Every other push to /(tabs)/items carries a filter param
            (`category` from here and the Portfolio breakdown, `collectionName`
            from sets-to-complete and the market screen), so without this the
            whole collection is reachable only by tapping the Items tab itself
            — and that tab is on its way off the bar. A category card answers
            "what's in Pokémon"; this answers "show me everything". */}
        {onAllItemsPress && !isEmpty && (
          <AnimatedPressable
            onPress={onAllItemsPress}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel="See all items in your collection, A to Z"
          >
            <Text style={[s.sectionAction, { color: theme.accent }]}>All items →</Text>
          </AnimatedPressable>
        )}
      </View>

      {loading ? (
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <SkeletonList count={3} type="row" />
        </View>
      ) : isEmpty ? (
        // Real empty state — no fabricated demo data. The breakdown is real
        // portfolio data from the backend; when the user has no items yet,
        // show a prompt instead of placeholder numbers.
        <View style={[s.breakdownCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[s.breakdownEmpty, { color: theme.muted }]}>
            Add items to your collection to see how their value breaks down by category.
          </Text>
        </View>
      ) : (
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
  // md (14), not sm/xs: this is a tap target and a route, and `xs` is banned
  // for anything a user needs to read (docs/ui-playbook.md type scale).
  sectionAction: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
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
