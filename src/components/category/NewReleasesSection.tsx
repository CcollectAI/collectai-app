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

      <View style={styles.grid}>
        {items.map((item) => (
          <AnimatedPressable
            key={item.id}
            style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}
            onPress={() => onItemPress?.(item)}
            accessibilityRole="button"
            accessibilityLabel={item.title}
          >
            <View style={[styles.imagePlaceholder, { backgroundColor: colors.accent + '18' }]}>
              <Ionicons name="cube-outline" size={20} color={colors.accent} />
            </View>
            <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={2}>
              {item.title}
            </Text>
            {item.estimated_price != null && (
              <Text style={[styles.price, { color: colors.accent }]}>
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
  card: { width: '30%', borderRadius: 10, borderWidth: 1, padding: 8, alignItems: 'center' },
  image: { width: 56, height: 56, borderRadius: 8, marginBottom: 6 },
  imagePlaceholder: { width: 56, height: 56, borderRadius: 8, marginBottom: 6, alignItems: 'center', justifyContent: 'center' },
  itemTitle: { fontSize: 11, fontWeight: '600', textAlign: 'center', lineHeight: 14 },
  price: { fontSize: 11, fontWeight: '700', marginTop: 2 },
});
