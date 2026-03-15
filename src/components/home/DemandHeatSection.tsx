/**
 * DemandHeatSection — "Hot Right Now" trending items on home screen.
 * Calls getDemandHeat() and displays top trending items by demand signals.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDemandHeat = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    collectorsApi.getDemandHeat()
      .then((data) => {
        if (!cancelled && Array.isArray(data?.items)) {
          setItems(data.items.slice(0, 10));
        }
      })
      .catch((err) => {
        logger.warn('[DemandHeat] fetch failed:', err);
        if (!cancelled) setError('Failed to load trending items');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    return fetchDemandHeat();
  }, [fetchDemandHeat]);

  if (loading) {
    return (
      <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.header}>
          <Ionicons name="flame-outline" size={18} color={colors.warning} />
          <Text style={[styles.title, { color: colors.text }]}>Hot Right Now</Text>
        </View>
        <ActivityIndicator size="small" color={colors.accent} style={{ paddingVertical: 20 }} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.header}>
          <Ionicons name="flame-outline" size={18} color={colors.warning} />
          <Text style={[styles.title, { color: colors.text }]}>Hot Right Now</Text>
        </View>
        <Text style={[styles.meta, { color: colors.muted, textAlign: 'center', paddingVertical: 8 }]}>{error}</Text>
        <AnimatedPressable onPress={fetchDemandHeat} style={{ alignSelf: 'center', paddingVertical: 6 }} accessibilityRole="button" accessibilityLabel="Retry loading trending items">
          <Text style={{ color: colors.accent, fontSize: textToken.sm, fontWeight: fw.semibold }}>Retry</Text>
        </AnimatedPressable>
      </View>
    );
  }

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
          accessibilityLabel={`Trending item ${i + 1}: ${item.title || item.item_key.replace(/-/g, ' ')}, ${item.category}, ${item.search_count} searches`}
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
    borderRadius: radius.md,
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
    fontSize: textToken.lg,
    fontWeight: fw.bold,
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
    borderRadius: radius.xs,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: {
    fontSize: textToken.sm,
    fontWeight: fw.bold,
  },
  info: {
    flex: 1,
  },
  itemName: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
  },
  meta: {
    fontSize: textToken.sm,
    marginTop: 1,
  },
});
