/**
 * FeaturedCollectionsSection — auto-rotating landscape carousel of the
 * category's catalog collections (grouped by set_code on the backend).
 *
 * DISCOVERY view: collections + counts come from the curated catalog
 * (GET /catalog/{id}/collections), NOT the signed-in user's ownership —
 * category pages are exploratory by design, so a fresh user still sees
 * real collections like "Gundam Wing · 87 items" instead of "0 items".
 */

import React, { useEffect, useState } from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
import { collectorsApi } from '@/api/collectorsApi';
import { type CategoryCollection } from '@/data/categories';
import logger from '@/utils/logger';

type CatalogCollection = {
  collection_key: string;
  display_name: string;
  total_items: number;
  cover_image?: string | null;
};

type Props = {
  // Retained for back-compat with the parent; used only as a last-resort
  // fallback if the catalog endpoint returns nothing.
  collections: CategoryCollection[];
  categoryId: string;
  title?: string;
  /** 'set' (default) groups by set_code; 'brand' groups by brand (e.g. watches). */
  groupBy?: 'set' | 'brand';
  onCollectionPress?: (collection: { collection_key: string; display_name: string }) => void;
};

export default React.memo(function FeaturedCollectionsSection({ collections, categoryId, title, groupBy, onCollectionPress }: Props) {
  const { colors } = useAppTheme();
  const [items, setItems] = useState<CatalogCollection[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getCatalogCollections(categoryId, 12, groupBy)
      .then((data) => {
        if (cancelled) return;
        const arr = Array.isArray(data?.collections) ? data.collections : [];
        setItems(arr);
      })
      .catch((err) => logger.warn('[FeaturedCollections] catalog fetch failed:', err))
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [categoryId, groupBy]);

  // Fall back to the static category collections only if the catalog has none.
  // Cap at 10 — big categories (e.g. pokemon) have 50+ sets, which made the
  // collections carousel an overwhelming, never-ending scroll.
  const MAX_COLLECTIONS = 10;
  const display: CatalogCollection[] = (items.length > 0
    ? items
    : (loaded
        ? collections.map((c) => ({
            collection_key: c.id,
            display_name: c.name,
            total_items: c.itemCount ?? 0,
          }))
        : [])).slice(0, MAX_COLLECTIONS);

  if (loaded && display.length === 0) return null;
  if (display.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="bookmark-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>{title ?? 'Featured Collections'}</Text>
      </View>

      <AutoRotatingCarousel intervalMs={6000} horizontalInset={30}>
        {display.map((col) => {
          // Only show a cover when this collection has its OWN distinct image.
          // We deliberately do NOT fall back to the category banner — that made
          // every coverless collection render the same image, which read as
          // cluttered, repeated, low-quality art. Coverless collections get a
          // clean icon-led card instead.
          const coverUri = (col.cover_image && col.cover_image.length > 0)
            ? col.cover_image
            : null;

          return (
            <AnimatedPressable
              key={col.collection_key}
              style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}
              onPress={() => onCollectionPress?.({ collection_key: col.collection_key, display_name: col.display_name })}
              accessibilityRole="button"
              accessibilityLabel={`Collection: ${col.display_name}`}
            >
              {coverUri ? (
                <Image
                  source={{ uri: coverUri }}
                  style={styles.cover}
                  resizeMode="cover"
                  accessibilityIgnoresInvertColors
                />
              ) : null}
              <View style={styles.cardTop}>
                <Ionicons name="library-outline" size={20} color={colors.accent} />
              </View>
              <Text style={[styles.collName, { color: colors.text }]} numberOfLines={2}>
                {col.display_name}
              </Text>
              <Text style={[styles.collMeta, { color: colors.muted }]} numberOfLines={1}>
                {col.total_items > 0 ? `${col.total_items} items` : 'Explore'}
              </Text>
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
    overflow: 'hidden',
  },
  cover: {
    width: '100%',
    height: 80,
    borderRadius: 8,
    marginBottom: 2,
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
});
