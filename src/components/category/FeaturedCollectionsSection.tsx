/**
 * FeaturedCollectionsSection — auto-rotating landscape carousel of pre-defined
 * collections for a category. Pulls completion progress from the backend.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
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

      <AutoRotatingCarousel intervalMs={6000} horizontalInset={30}>
        {collections.map((col) => {
          const prog = progress[col.name.toLowerCase().replace(/\s+/g, '_')];
          const owned = prog?.owned_count ?? 0;
          const total = col.itemCount || prog?.total_items || 0;
          const pct = prog?.completion_pct ?? 0;
          const hasProgress = total > 0 && pct > 0;
          const isComplete = pct >= 100;

          return (
            <AnimatedPressable
              key={col.name}
              style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}
              onPress={() => onCollectionPress?.(col.name)}
              accessibilityRole="button"
              accessibilityLabel={`Collection: ${col.name}`}
            >
              <View style={styles.cardTop}>
                <Ionicons name="library-outline" size={20} color={colors.accent} />
                {hasProgress && (
                  <View style={[styles.badge, { backgroundColor: isComplete ? colors.success + '20' : colors.accent + '18' }]}>
                    <Text style={[styles.badgeText, { color: isComplete ? colors.success : colors.accent }]}>
                      {Math.round(pct)}%
                    </Text>
                  </View>
                )}
              </View>
              <Text style={[styles.collName, { color: colors.text }]} numberOfLines={2}>
                {col.name}
              </Text>
              <Text style={[styles.collMeta, { color: colors.muted }]} numberOfLines={1}>
                {total > 0 ? `${owned} of ${total} owned` : `${col.itemCount} items`}
              </Text>
              {hasProgress && (
                <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
                  <View
                    style={[
                      styles.progressFill,
                      {
                        backgroundColor: isComplete ? colors.success : colors.accent,
                        width: `${Math.min(100, Math.round(pct))}%`,
                      },
                    ]}
                  />
                </View>
              )}
            </AnimatedPressable>
          );
        })}
      </AutoRotatingCarousel>
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
  card: {
    marginHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 18,
    paddingHorizontal: 16,
    minHeight: 150,
    justifyContent: 'space-between',
    gap: 10,
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
  collName: {
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 22,
  },
  collMeta: {
    fontSize: 12,
    fontWeight: '500',
  },
  progressTrack: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
});
