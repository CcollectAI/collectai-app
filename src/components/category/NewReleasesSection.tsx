/**
 * NewReleasesSection — shows recently added/released items for a category.
 * Fetches from catalog browse endpoint sorted by newest.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';

type NewItem = {
  id: string;
  title: string;
  estimated_price?: number;
  year?: string;
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
    collectorsApi.browseCatalogItems(categoryId, { limit: 6 })
      .then((data) => {
        if (cancelled) return;
        const arr = Array.isArray(data?.items) ? data.items : [];
        setItems(arr.slice(0, 6).map((i) => ({
          id: i.id,
          title: i.title,
          estimated_price: i.estimated_price ?? undefined,
        })));
      })
      .catch((err) => logger.warn('[NewReleases] fetch failed:', err));
    return () => { cancelled = true; };
  }, [categoryId]);

  if (items.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="sparkles-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>New Releases</Text>
      </View>

      {/* Text-only cards — catalog image_url was removed in R50k (Wikimedia
          coverage was too patchy, 50/50 placeholders looked buggy).
          User-uploaded photos only show on the items tab. */}
      <View style={styles.grid}>
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
            <Text
              style={[styles.itemTitle, { color: colors.text }]}
              numberOfLines={2}
              ellipsizeMode="tail"
            >
              {item.title}
            </Text>
            {item.estimated_price != null && (
              <Text
                style={[styles.price, { color: colors.accent }]}
                numberOfLines={1}
                ellipsizeMode="tail"
              >
                {currency === 'EUR' ? '€' : '$'}{item.estimated_price.toFixed(0)}
              </Text>
            )}
          </AnimatedPressable>
        ))}
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  container: { borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 16 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  title: { fontSize: 16, fontWeight: '700' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  card: {
    flexBasis: '31%',
    flexGrow: 0,
    flexShrink: 0,
    minWidth: 96,
    borderRadius: 10,
    borderWidth: 1,
    paddingVertical: 12,
    paddingHorizontal: 8,
    alignItems: 'flex-start',
    gap: 6,
    minHeight: 88,
  },
  newBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  newBadgeText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  itemTitle: { fontSize: 12, fontWeight: '600', lineHeight: 15 },
  price: { fontSize: 12, fontWeight: '700', marginTop: 'auto' },
});
