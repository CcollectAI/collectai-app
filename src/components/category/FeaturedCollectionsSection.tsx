/**
 * FeaturedCollectionsSection — Shows pre-defined collections for a category.
 * Uses static collection data from categories.ts + backend completion progress.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import type { CategoryCollection } from '@/data/categories';
import logger from '@/utils/logger';

type CollectionProgress = {
  collection_id: string;
  collection_key?: string;
  owned_count: number;
  total_items: number;
  completion_pct: number;
};

type Props = {
  collections: CategoryCollection[];
  categoryId: string;
  onCollectionPress?: (name: string) => void;
};

export default React.memo(function FeaturedCollectionsSection({ collections, categoryId, onCollectionPress }: Props) {
  const { colors } = useAppTheme();
  const [progress, setProgress] = useState<Record<string, CollectionProgress>>({});

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getUserCollectionProgress(categoryId)
      .then((data) => {
        if (cancelled) return;
        const items = Array.isArray((data as { progress?: unknown[] })?.progress)
          ? (data as { progress: CollectionProgress[] }).progress
          : [];
        const map: Record<string, CollectionProgress> = {};
        for (const p of items) {
          if (p.collection_key) map[p.collection_key] = p;
        }
        setProgress(map);
      })
      .catch((err) => logger.warn('[FeaturedCollections] progress fetch failed:', err));
    return () => { cancelled = true; };
  }, [categoryId]);

  if (collections.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="bookmark-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Featured Collections</Text>
      </View>

      {collections.map((col) => {
        const prog = progress[col.name.toLowerCase().replace(/\s+/g, '_')];
        const owned = prog?.owned_count ?? 0;
        const total = col.itemCount || prog?.total_items || 0;
        const pct = prog?.completion_pct ?? 0;

        return (
          <AnimatedPressable
            key={col.name}
            onPress={() => onCollectionPress?.(col.name)}
            style={[styles.row, { borderBottomColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Collection: ${col.name}`}
          >
            <View style={styles.info}>
              <Text style={[styles.collName, { color: colors.text }]} numberOfLines={1}>
                {col.name}
              </Text>
              <Text style={[styles.collMeta, { color: colors.muted }]}>
                {total > 0 ? `${owned}/${total} items` : `${col.itemCount} items`}
              </Text>
            </View>
            {total > 0 && pct > 0 ? (
              <View style={[styles.badge, { backgroundColor: pct >= 100 ? colors.success + '20' : colors.accent + '15' }]}>
                <Text style={[styles.badgeText, { color: pct >= 100 ? colors.success : colors.accent }]}>
                  {Math.round(pct)}%
                </Text>
              </View>
            ) : (
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            )}
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
  },
  info: {
    flex: 1,
  },
  collName: {
    fontSize: 14,
    fontWeight: '600',
  },
  collMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 8,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '700',
  },
});
