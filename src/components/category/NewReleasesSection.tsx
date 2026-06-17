/**
 * NewReleasesSection — auto-rotating "Featured in Catalog" carousel of catalog
 * items for a category. Fetches priced items from the catalog browse endpoint
 * (priced_only) so every card has a real market comp. Labelled "Featured"
 * rather than "New" since ordering is not strictly recency-based.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
import { browseCatalogItemsCached } from '@/data/catalogBrowseCache';
import logger from '@/utils/logger';

type NewItem = {
  id: string;
  title: string;
  estimated_price?: number;
  year?: string;
  imageUrl?: string;
};

type Props = {
  categoryId: string;
  currency?: string;
  onItemPress?: (item: NewItem) => void;
};

export default React.memo(function NewReleasesSection({ categoryId, currency = 'EUR', onItemPress }: Props) {
  const { colors } = useAppTheme();
  const [items, setItems] = useState<NewItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    // pricedOnly => backend only returns items with a recent market comp, so
    // the carousel never shows a price-less "New in Catalog" card. Over-fetch
    // a little and keep a FE price filter as a guard in case an older backend
    // ignores the flag.
    browseCatalogItemsCached(categoryId, { limit: 12, pricedOnly: true })
      .then((data) => {
        if (cancelled) return;
        const arr = Array.isArray(data?.items) ? data.items : [];
        setItems(
          arr
            .filter((i) => i.estimated_price != null)
            .slice(0, 6)
            .map((i) => ({
              id: i.id,
              title: i.title,
              estimated_price: i.estimated_price ?? undefined,
              imageUrl: i.image_url ?? undefined,
            })),
        );
      })
      .catch((err) => logger.warn('[NewReleases] fetch failed:', err));
    return () => { cancelled = true; };
  }, [categoryId]);

  if (items.length === 0) return null;

  const currencySymbol = currency === 'EUR' ? '€' : '$';

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="sparkles-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Featured in Catalog</Text>
      </View>

      <AutoRotatingCarousel intervalMs={5000} horizontalInset={30}>
        {items.map((item) => (
          <AnimatedPressable
            key={item.id}
            style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}
            onPress={() => onItemPress?.(item)}
            accessibilityRole="button"
            accessibilityLabel={item.title}
          >
            <View style={[styles.newBadge, { backgroundColor: colors.accent + '18' }]}>
              <Text style={[styles.newBadgeText, { color: colors.accent }]}>NEW</Text>
            </View>
            {item.imageUrl ? (
              <Image
                source={{ uri: item.imageUrl }}
                style={[styles.thumb, { backgroundColor: colors.card }]}
                resizeMode="contain"
                accessibilityIgnoresInvertColors
              />
            ) : (
              <View style={[styles.thumb, styles.thumbPlaceholder, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Ionicons name="image-outline" size={26} color={colors.muted} />
              </View>
            )}
            <Text
              style={[styles.itemTitle, { color: colors.text }]}
              numberOfLines={2}
              ellipsizeMode="tail"
            >
              {item.title}
            </Text>
            {item.estimated_price != null && (
              <Text style={[styles.price, { color: colors.accent }]} numberOfLines={1}>
                {currencySymbol}{item.estimated_price.toFixed(0)}
              </Text>
            )}
          </AnimatedPressable>
        ))}
      </AutoRotatingCarousel>
    </View>
  );
});

const styles = StyleSheet.create({
  container: { borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 16 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  title: { fontSize: 16, fontWeight: '700' },
  card: {
    marginHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 18,
    paddingHorizontal: 16,
    alignItems: 'flex-start',
    gap: 10,
    minHeight: 140,
    justifyContent: 'space-between',
  },
  newBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  newBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  thumb: { width: '100%', height: 90, borderRadius: 8 },
  thumbPlaceholder: { alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  itemTitle: { fontSize: 16, fontWeight: '700', lineHeight: 20 },
  price: { fontSize: 18, fontWeight: '800' },
});
