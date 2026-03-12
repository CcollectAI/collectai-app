/**
 * DemandHeatSection — "Hot Right Now" trending items on home screen.
 * Calls getDemandHeat() and displays top trending items by demand signals.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';

type HeatItem = {
  item_key: string;
  title: string;
  category: string;
  demand_score: number;
  search_count: number;
};

export const DemandHeatSection = React.memo(function DemandHeatSection() {
  const { colors } = useAppTheme();
  const [items, setItems] = useState<HeatItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getDemandHeat()
      .then((data) => {
        if (!cancelled && Array.isArray(data?.items)) {
          setItems(data.items.slice(0, 5));
        }
      })
      .catch((err) => logger.warn('[DemandHeat] fetch failed:', err));
    return () => { cancelled = true; };
  }, []);

  if (items.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="flame-outline" size={18} color={colors.warning} />
        <Text style={[styles.title, { color: colors.text }]}>Hot Right Now</Text>
      </View>
      {items.map((item, i) => (
        <AnimatedPressable
          key={item.item_key}
          onPress={() => router.push(`/(tabs)/marketplace`)}
          style={[styles.row, i < items.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`Trending: ${item.item_key}`}
        >
          <View style={[styles.rank, { backgroundColor: i < 3 ? colors.warning + '20' : colors.border + '40' }]}>
            <Text style={[styles.rankText, { color: i < 3 ? colors.warning : colors.muted }]}>#{i + 1}</Text>
          </View>
          <View style={styles.info}>
            <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>{item.title || item.item_key.replace(/-/g, ' ')}</Text>
            <Text style={[styles.meta, { color: colors.muted }]}>{item.category} · {item.search_count} searches</Text>
          </View>
          <Ionicons name="trending-up" size={16} color={colors.success} />
        </AnimatedPressable>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
  },
  rank: {
    width: 32,
    height: 24,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: {
    fontSize: 12,
    fontWeight: '700',
  },
  info: {
    flex: 1,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  meta: {
    fontSize: 11,
    marginTop: 1,
  },
});
