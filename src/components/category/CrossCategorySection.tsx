/**
 * CrossCategorySection — "Collectors who have X also collect Y" social proof.
 * Shows related categories that other collectors of this category tend to own.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import { CATEGORY_VISUAL } from '@/data/categories';
import logger from '@/utils/logger';

type Correlation = {
  category: string;
  collector_count: number;
  overlap_pct: number;
};

type Props = {
  categoryId: string;
  onCategoryPress: (categoryId: string) => void;
};

export default React.memo(function CrossCategorySection({ categoryId, onCategoryPress }: Props) {
  const { colors } = useAppTheme();
  const [correlations, setCorrelations] = useState<Correlation[]>([]);

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getCategoryCrossCorrelation(categoryId)
      .then((data) => {
        if (cancelled) return;
        const arr = Array.isArray((data as { correlations?: unknown[] })?.correlations)
          ? (data as { correlations: Correlation[] }).correlations
          : [];
        setCorrelations(arr.slice(0, 5));
      })
      .catch((err) => logger.warn('[CrossCategory] fetch failed:', err));
    return () => { cancelled = true; };
  }, [categoryId]);

  if (correlations.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="people-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Also Collected By</Text>
      </View>

      {correlations.map((c) => {
        const visual = CATEGORY_VISUAL[c.category as keyof typeof CATEGORY_VISUAL];
        const accent = visual?.accentColor ?? colors.accent;
        return (
          <AnimatedPressable
            key={c.category}
            style={[styles.row, { borderBottomColor: colors.border }]}
            onPress={() => onCategoryPress(c.category)}
            accessibilityRole="button"
            accessibilityLabel={`${c.category.replace(/_/g, ' ')}: ${c.overlap_pct}% overlap`}
          >
            <View style={[styles.dot, { backgroundColor: accent }]} />
            <View style={styles.info}>
              <Text style={[styles.catName, { color: colors.text }]} numberOfLines={1}>
                {c.category.replace(/_/g, ' ')}
              </Text>
              <Text style={[styles.catMeta, { color: colors.muted }]}>
                {c.overlap_pct}% of collectors also have this
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={14} color={colors.muted} />
          </AnimatedPressable>
        );
      })}
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
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 10,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  info: {
    flex: 1,
  },
  catName: {
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  catMeta: {
    fontSize: 11,
    marginTop: 2,
  },
});
