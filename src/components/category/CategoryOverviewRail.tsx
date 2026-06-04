/**
 * CategoryOverviewRail — THE single category carousel.
 *
 * Replaces the old pile of carousels (Spotlight / New Releases / Items /
 * Featured Collections / Browse Catalog). It's a browsable overview of the
 * whole category catalog ("what exists"), with sort chips, that funnels every
 * tap into the museum detail (→ "Where to buy" affiliate links).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, Image, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';
import type { CatalogItemData } from '@/components/CatalogBrowseSection';
import type { AppTheme } from '@/hooks/useAppTheme';

type SortKey = 'value' | 'all' | 'set';

type Props = {
  categoryId: string;
  total?: number;
  accentColor: string;
  colors: AppTheme['colors'];
  onItemPress: (item: CatalogItemData) => void;
  onSeeAll: () => void;
};

const CHIPS: { key: SortKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: 'value', label: 'Most valuable', icon: 'diamond-outline' },
  { key: 'all', label: 'All', icon: 'grid-outline' },
  { key: 'set', label: 'By set', icon: 'albums-outline' },
];

function CategoryOverviewRail({ categoryId, total, accentColor, colors, onItemPress, onSeeAll }: Props) {
  const [sort, setSort] = useState<SortKey>('value');
  const [items, setItems] = useState<CatalogItemData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        // "Most valuable" pulls priced items; the others pull a general page.
        const res = await collectorsApi.browseCatalogItems(categoryId, {
          limit: 24,
          pricedOnly: sort === 'value',
        });
        let list = (res?.items ?? []) as CatalogItemData[];
        if (sort === 'value') {
          list = [...list].sort((a, b) => (b.estimated_price ?? 0) - (a.estimated_price ?? 0));
        } else if (sort === 'set') {
          list = [...list].sort((a, b) => (a.set_code ?? '').localeCompare(b.set_code ?? ''));
        }
        if (!cancelled) setItems(list.slice(0, 20));
      } catch (e) {
        logger.warn('[CategoryOverviewRail] fetch failed:', e);
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [categoryId, sort]);

  const fmtPrice = useCallback((p: number | null) => (p == null ? null : `~€${Math.round(p)}`), []);

  return (
    <View style={styles.wrap}>
      <View style={styles.head}>
        <Text style={[styles.title, { color: colors.text }]}>
          The {''}catalog{total ? ` · ${total.toLocaleString()} items` : ''}
        </Text>
        <AnimatedPressable onPress={onSeeAll} accessibilityRole="button" accessibilityLabel="See all items">
          <Text style={[styles.seeAll, { color: accentColor }]}>See all →</Text>
        </AnimatedPressable>
      </View>

      {/* sort chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {CHIPS.map((c) => {
          const active = c.key === sort;
          return (
            <AnimatedPressable
              key={c.key}
              onPress={() => setSort(c.key)}
              style={[styles.chip, { borderColor: colors.border, backgroundColor: colors.card },
                active && { backgroundColor: accentColor, borderColor: accentColor }]}
              accessibilityRole="button"
              accessibilityLabel={`Sort by ${c.label}`}
            >
              <Ionicons name={c.icon} size={13} color={active ? '#fff' : colors.muted} />
              <Text style={[styles.chipText, { color: active ? '#fff' : colors.muted }]}>{c.label}</Text>
            </AnimatedPressable>
          );
        })}
      </ScrollView>

      {loading ? (
        <ActivityIndicator color={accentColor} style={{ marginVertical: 28 }} />
      ) : items.length === 0 ? (
        <Text style={[styles.empty, { color: colors.muted }]}>No catalog items for this category yet.</Text>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.rail}>
          {items.map((it) => (
            <AnimatedPressable
              key={it.id}
              style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => onItemPress(it)}
              accessibilityRole="button"
              accessibilityLabel={`View ${it.title}`}
            >
              {it.image_url ? (
                <Image source={{ uri: it.image_url }} style={styles.art} resizeMode="cover" accessibilityIgnoresInvertColors />
              ) : (
                <View style={[styles.art, styles.artEmpty, { backgroundColor: accentColor + '12' }]}>
                  <Ionicons name="cube-outline" size={26} color={accentColor} />
                </View>
              )}
              <View style={styles.meta}>
                <Text style={[styles.nm, { color: colors.text }]} numberOfLines={2}>{it.title}</Text>
                {fmtPrice(it.estimated_price) ? (
                  <Text style={[styles.pr, { color: accentColor }]}>{fmtPrice(it.estimated_price)}</Text>
                ) : (
                  <Text style={[styles.tag, { color: colors.muted }]}>{it.rarity || it.set_code || 'Explore'}</Text>
                )}
              </View>
            </AnimatedPressable>
          ))}
          {/* See-all tile */}
          <AnimatedPressable
            style={[styles.card, styles.seeAllTile, { borderColor: accentColor }]}
            onPress={onSeeAll}
            accessibilityRole="button"
            accessibilityLabel="See all items"
          >
            <Text style={[styles.seeAllTileText, { color: accentColor }]}>
              See all{total ? `\n${total.toLocaleString()}` : ''} →
            </Text>
          </AnimatedPressable>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 18 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, marginBottom: 8 },
  title: { fontSize: 16, fontWeight: '800' },
  seeAll: { fontSize: 13, fontWeight: '600' },
  chips: { gap: 8, paddingHorizontal: 16, paddingBottom: 10 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 7, paddingHorizontal: 13, borderRadius: 999, borderWidth: 1 },
  chipText: { fontSize: 12.5, fontWeight: '600' },
  rail: { gap: 12, paddingHorizontal: 16, paddingBottom: 4 },
  card: { width: 140, borderRadius: 14, borderWidth: 1, overflow: 'hidden' },
  art: { width: '100%', height: 120 },
  artEmpty: { alignItems: 'center', justifyContent: 'center' },
  meta: { padding: 10 },
  nm: { fontSize: 12.5, fontWeight: '700' },
  pr: { fontSize: 15, fontWeight: '900', marginTop: 4 },
  tag: { fontSize: 11, marginTop: 4 },
  seeAllTile: { width: 110, alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed', backgroundColor: 'transparent' },
  seeAllTileText: { fontSize: 13, fontWeight: '700', textAlign: 'center' },
  empty: { fontSize: 13, paddingHorizontal: 16, paddingVertical: 12 },
});

export default React.memo(CategoryOverviewRail);
