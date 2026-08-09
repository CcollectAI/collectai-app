/**
 * "Popular in Your Region" section for the Marketplace screen.
 *
 * Shows trending items near the user based on regional collector activity.
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

/**
 * ⚠️ This section is currently NEVER RENDERED, and that is deliberate for now.
 *
 * `marketplace.tsx` populates it from `GET /data-moat/demand-heat/by-region`,
 * reading `resp.items` — but that endpoint returns `{regions: [...]}`, an
 * aggregate grouped by `region, country_code` with no `item_key` at all. So
 * `items` is always `undefined`, the array stays empty, and the guard below
 * returns null. A real reader/writer mismatch (verified 2026-07-30).
 *
 * It was NOT wired up, because the data does not support it yet: over 7 days
 * `demand_signals` held 68 rows of which only **9 had a region**, across 8
 * users, and a per-item-by-region query returned 4 rows — 3 of them test
 * artifacts (`slot freed`, `test query 2/3`) with a NULL category. Surfacing
 * that as "Popular in Your Region" would show junk.
 *
 * To wire it later: return an `items` array (item_key, category, signal_count,
 * region) from that endpoint alongside `regions` — additive, so nothing else
 * breaks — and only after real regional signal volume exists.
 */
export interface RegionalDemandItem {
  item_key: string;
  /** Nullable in practice: `demand_signals.category` is NULL on many rows. */
  category: string | null;
  signal_count: number;
  region: string;
}

interface RegionalInsightsSectionProps {
  items: RegionalDemandItem[];
  onSearchItem: (query: string) => void;
}

export const RegionalInsightsSection = React.memo(function RegionalInsightsSection({
  items,
  onSearchItem,
}: RegionalInsightsSectionProps) {
  const { colors } = useAppTheme();

  if (items.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        <Ionicons name="location-outline" size={16} color={colors.accent} /> Popular in Your Region
      </Text>
      <Text style={[styles.sectionSubtitle, { color: colors.muted }]}>Trending near you based on collector activity</Text>
      <View style={{ gap: 6, marginTop: 8 }}>
        {items.map((item) => (
          <AnimatedPressable
            key={item.item_key}
            style={[styles.demandCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              onSearchItem(item.item_key.replace(/-/g, ' '));
            }}
            accessibilityRole="button"
            accessibilityLabel={`Search for ${item.item_key.replace(/-/g, ' ')}`}
          >
            <View style={[styles.demandRank, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name="location" size={14} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.demandTitle, { color: colors.text }]} numberOfLines={1}>{item.item_key.replace(/-/g, ' ')}</Text>
              {/* `category` is NULL on a large share of demand_signals rows;
                  the bare .replace() here was a TypeError waiting for whoever
                  wires this section up. */}
              <Text style={[styles.demandMeta, { color: colors.muted }]}>
                {item.category ? `${item.category.replace(/_/g, ' ')} · ` : ''}{item.region}
              </Text>
            </View>
            <View style={[styles.demandScore, { backgroundColor: colors.warning + '15' }]}>
              <Text style={[styles.demandScoreText, { color: colors.warning }]}>{item.signal_count}</Text>
            </View>
          </AnimatedPressable>
        ))}
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 6,
  },
  sectionSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  demandCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 10,
    borderWidth: 1,
    padding: 10,
    gap: 10,
  },
  demandRank: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  demandTitle: {
    fontSize: 13,
    fontWeight: '600',
  },
  demandMeta: {
    fontSize: 11,
    marginTop: 1,
  },
  demandScore: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  demandScoreText: {
    fontSize: 12,
    fontWeight: '600',
  },
});
