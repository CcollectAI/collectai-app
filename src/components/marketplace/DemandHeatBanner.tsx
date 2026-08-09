/**
 * "Hot Right Now" demand heat display section for the Marketplace screen.
 *
 * Shows the most-searched items across collectors with rank badges and demand scores.
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

export interface DemandHeatItem {
  item_key: string;
  title: string;
  category: string;
  demand_score: number;
  search_count: number;
}

interface DemandHeatBannerProps {
  items: DemandHeatItem[];
  onSearchItem: (title: string) => void;
}

export const DemandHeatBanner = React.memo(function DemandHeatBanner({
  items,
  onSearchItem,
}: DemandHeatBannerProps) {
  const { colors } = useAppTheme();

  if (items.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        <Ionicons name="flame-outline" size={16} color={colors.warning} /> Hot Right Now
      </Text>
      <Text style={[styles.sectionSubtitle, { color: colors.muted }]}>Most searched items across collectors</Text>
      <View style={{ gap: 6, marginTop: 8 }}>
        {items.map((item, i) => (
          <AnimatedPressable
            // `item_key` is NOT unique on its own. The rows come from
            // mv_demand_heat, whose grain is (category, item_key,
            // signal_type), and sentinel keys recur across categories —
            // live data has `general` under both `unknown` and `mtg`.
            // Keying on item_key alone produced React's "two children with
            // the same key" warning 14x on the marketplace tab.
            key={`${item.category}::${item.item_key}`}
            style={[styles.demandCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              onSearchItem(item.title);
            }}
            accessibilityRole="button"
            accessibilityLabel={`Search for ${item.title}`}
          >
            <View style={[styles.demandRank, { backgroundColor: i < 3 ? colors.warning + '20' : colors.border + '40' }]}>
              <Text style={[styles.demandRankText, { color: i < 3 ? colors.warning : colors.muted }]}>#{i + 1}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.demandTitle, { color: colors.text }]} numberOfLines={1}>{item.title}</Text>
              <Text style={[styles.demandMeta, { color: colors.muted }]}>{item.category} · {item.search_count} searches</Text>
            </View>
            <View style={[styles.demandScore, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="trending-up-outline" size={12} color={colors.accent} />
              <Text style={[styles.demandScoreText, { color: colors.accent }]}>{item.demand_score}</Text>
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
  demandRankText: {
    fontSize: 12,
    fontWeight: '700',
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
