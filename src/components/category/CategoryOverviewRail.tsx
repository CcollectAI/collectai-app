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

type SortKey = 'all' | 'value' | 'newest' | 'set';

type Props = {
  categoryId: string;
  /** Optional display name for the header ("The Pokémon catalog"). */
  categoryName?: string;
  accentColor: string;
  colors: AppTheme['colors'];
  onItemPress: (item: CatalogItemData) => void;
  onSeeAll: () => void;
};

// Mockup chip order (All / Most valuable / Newest / By set); default SORT is
// still 'value' — commission is a % of price, so the highest-earning items
// lead while the chips keep the whole catalog reachable.
const CHIPS: { key: SortKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: 'all', label: 'All', icon: 'grid-outline' },
  { key: 'value', label: 'Most valuable', icon: 'diamond-outline' },
  { key: 'newest', label: 'Newest', icon: 'sparkles-outline' },
  { key: 'set', label: 'By set', icon: 'albums-outline' },
];

function CategoryOverviewRail({ categoryId, categoryName, accentColor, colors, onItemPress, onSeeAll }: Props) {
  const [sort, setSort] = useState<SortKey>('value');
  const [items, setItems] = useState<CatalogItemData[]>([]);
  // Full catalog size for the category ("what exists"), from the BE's real
  // total — drives "· 1,247 items" in the header and the See-all tile.
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        // Sorting is server-side now: 'value' ranks by latest comp price
        // (priced items only), the rest page the full catalog.
        const res = await collectorsApi.browseCatalogItems(categoryId, {
          limit: 20,
          pricedOnly: sort === 'value',
          sort: sort === 'all' ? 'title' : sort,
        });
        if (!cancelled) {
          setItems((res?.items ?? []) as CatalogItemData[]);
          if (typeof res?.total === 'number') setTotal(res.total);
        }
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
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          The {categoryName ? `${categoryName} ` : ''}catalog{total ? ` · ${total.toLocaleString()} items` : ''}
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
  title: { fontSize: 16, fontWeight: '800', flex: 1, marginRight: 8 },
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
