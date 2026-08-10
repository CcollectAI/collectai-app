/**
 * CategoryPerformanceSection — Category statistics dashboard for analytics screen.
 *
 * Shows per-category stats with health dots and 7d trends.
 * Extracted from app/analytics.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, type Href } from 'expo-router';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { radius, text, fontWeight, shadow } from '@/theme/tokens';

/**
 * Shape of one row from `GET /portfolio/category-stats`.
 *
 * `avg_value` was REMOVED on 2026-08-10. The server averaged unpriced items in
 * as EUR 0, so for the 40+ categories with no sold-comp source (watches,
 * whiskey, lego …) the "average" was mostly a count of what we don't know. It
 * is replaced by a median plus the actual spread.
 *
 * median/min/max are `number | null` — null means NOTHING in that category has
 * a price. That is deliberately not 0: a category we cannot value must not
 * claim to be worth nothing.
 */
interface CategoryStat {
  category: string;
  item_count: number;
  priced_count: number;
  total_value: number;
  median_value: number | null;
  min_item_value: number | null;
  max_item_value: number | null;
  change_7d: number;
  change_7d_pct: number;
  trend: string;
}

interface CategoryHealth {
  category: string;
  volatility: number;
  trend_strength: number;
  health: string;
}

interface CategoryPerformanceSectionProps {
  categoryStats: CategoryStat[];
  categoryHealth: CategoryHealth[];
}

function CategoryPerformanceSectionInner({
  categoryStats,
  categoryHealth,
}: CategoryPerformanceSectionProps) {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  if (categoryStats.length === 0) return null;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Ionicons name="grid-outline" size={18} color={colors.accent} />
        <Text style={[styles.cardTitle, { color: colors.text }]}>Category Performance</Text>
        <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{categoryStats.length} categories</Text>
      </View>
      {categoryStats.slice(0, 8).map((cat) => {
        const trendIcon = cat.trend === 'up' ? 'trending-up' : cat.trend === 'down' ? 'trending-down' : 'remove-outline';
        const trendColor = cat.trend === 'up' ? colors.success : cat.trend === 'down' ? colors.danger : colors.muted;
        const healthEntry = categoryHealth.find((h) => h.category === cat.category);
        const healthColor = healthEntry?.health === 'green' ? colors.success : healthEntry?.health === 'yellow' ? colors.warning : healthEntry?.health === 'red' ? colors.danger : colors.muted;
        return (
          <AnimatedPressable
            key={cat.category}
            style={[styles.catStatRow, { borderBottomColor: colors.border }]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push(`/categories/${encodeURIComponent(cat.category)}` as Href); }}
            accessibilityRole="button"
            accessibilityLabel={`${cat.category.replace(/_/g, ' ')}: ${cat.item_count} items, ${formatPrice(cat.total_value, settings.currency ?? 'EUR')}, 7d ${cat.trend}`}
          >
            <View style={styles.catStatLeft}>
              <View style={styles.catStatNameRow}>
                <Text style={[styles.catStatName, { color: colors.text }]} numberOfLines={1}>
                  {cat.category.replace(/_/g, ' ')}
                </Text>
                {healthEntry && (
                  <View style={[styles.healthDot, { backgroundColor: healthColor }]} />
                )}
              </View>
              {/* Median + spread, not a mean. A EUR 40 Seiko beside a EUR 18,000
                  Daytona has no meaningful average, and the old one also counted
                  every unpriced item as EUR 0. When nothing in the category is
                  priced we say so rather than printing a number. The spread is
                  only shown once min and max actually differ — on a
                  single-priced category it would just repeat the median. */}
              <Text style={[styles.catStatMeta, { color: colors.muted }]}>
                {cat.median_value == null
                  ? `${cat.item_count} items · not yet priced`
                  : cat.min_item_value != null &&
                    cat.max_item_value != null &&
                    cat.max_item_value > cat.min_item_value
                    ? `${cat.item_count} items · median ${formatPrice(cat.median_value, settings.currency ?? 'EUR')} · ${formatPrice(cat.min_item_value, settings.currency ?? 'EUR')}–${formatPrice(cat.max_item_value, settings.currency ?? 'EUR')}`
                    : `${cat.item_count} items · median ${formatPrice(cat.median_value, settings.currency ?? 'EUR')}`}
              </Text>
            </View>
            <View style={styles.catStatRight}>
              <Text style={[styles.catStatValue, { color: colors.text }]}>
                {formatPrice(cat.total_value, settings.currency ?? 'EUR')}
              </Text>
              <View style={styles.catStatTrend}>
                <Ionicons name={trendIcon} size={12} color={trendColor} />
                <Text style={[styles.catStatPct, { color: trendColor }]}>
                  {cat.change_7d_pct > 0 ? '+' : ''}{cat.change_7d_pct.toFixed(1)}%
                </Text>
              </View>
            </View>
          </AnimatedPressable>
        );
      })}
    </View>
  );
}

export const CategoryPerformanceSection = React.memo(CategoryPerformanceSectionInner);

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
    ...shadow.card,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  cardSubtitle: {
    fontSize: text.md,
  },
  catStatRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  catStatLeft: {
    flex: 1,
    marginRight: 12,
  },
  catStatNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  catStatName: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    textTransform: 'capitalize',
  },
  healthDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  catStatMeta: {
    fontSize: text.sm,
    marginTop: 2,
  },
  catStatRight: {
    alignItems: 'flex-end',
  },
  catStatValue: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  catStatTrend: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginTop: 2,
  },
  catStatPct: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
});
