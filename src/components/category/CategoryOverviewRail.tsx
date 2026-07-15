/**
 * CategoryOverviewRail — THE single category carousel.
 *
 * Replaces the old pile of carousels (Spotlight / New Releases / Items /
 * Featured Collections / Browse Catalog). It's a browsable overview of the
 * whole category catalog ("what exists") that funnels every tap into the
 * museum detail (→ "Where to buy" affiliate links).
 *
 * Mockup fidelity (web/category-redesign-preview.html): the rail lives in a
 * white card with a tiffany border; section label is the mockup's `.lbl`
 * (uppercase, 11/800, letter-spaced); prices use deep tiffany #2C7873; the
 * see-all tile carries the light tiffany wash. Sort state is OWNED BY THE
 * PAGE (CategorySortChips sits above this card, like the mockup) and comes
 * in via the `sort` prop.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, Image, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { browseCatalogItemsCached } from '@/data/catalogBrowseCache';
import { cleanCatalogTitle } from '@/lib/catalogPresentation';
import { formatPrice } from '@/lib/format';
import { colors as tokens } from '@/theme/tokens';
import logger from '@/utils/logger';
import type { CatalogItemData } from '@/components/CatalogBrowseSection';
import type { CatalogSortKey } from '@/components/category/CategorySortChips';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  categoryId: string;
  /** Optional display name for the header ("THE POKÉMON CATALOG"). */
  categoryName?: string;
  /** Overrides the header label entirely (e.g. "🗂 BY SET"). */
  label?: string;
  /** Sort selected in the page-level CategorySortChips. */
  sort: CatalogSortKey;
  accentColor: string;
  colors: AppTheme['colors'];
  onItemPress: (item: CatalogItemData) => void;
  onSeeAll: () => void;
  /** Reports the live catalog total (drives the "All 1,247" chip + see-all tile). */
  onTotal?: (total: number) => void;
};

function CategoryOverviewRail({ categoryId, categoryName, label, sort, accentColor, colors, onItemPress, onSeeAll, onTotal }: Props) {
  const [items, setItems] = useState<CatalogItemData[]>([]);
  // Full catalog size for the category ("what exists"), from the BE's real
  // total — drives the see-all tile and is reported up for the "All" chip.
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        // Sorting is server-side: 'value' ranks by latest comp price
        // (priced items only), the rest page the full catalog.
        const res = await browseCatalogItemsCached(categoryId, {
          limit: 20,
          pricedOnly: sort === 'value',
          sort: sort === 'all' ? 'title' : sort,
        });
        if (!cancelled) {
          setItems((res?.items ?? []) as CatalogItemData[]);
          if (typeof res?.total === 'number') {
            setTotal(res.total);
            onTotal?.(res.total);
          }
        }
      } catch (e) {
        logger.warn('[CategoryOverviewRail] fetch failed:', e);
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // onTotal is a state setter from the page; identity-stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryId, sort]);

  const fmtPrice = useCallback((p: number | null) => (p == null ? null : `~${formatPrice(p)}`), []);

  return (
    <View style={[styles.wrap, { backgroundColor: colors.card }]}>
      <View style={styles.head}>
        <Text style={[styles.label, { color: colors.muted }]} numberOfLines={1}>
          {label ?? `📚 THE ${categoryName ? `${categoryName.toUpperCase()} ` : ''}CATALOG`}
        </Text>
        <AnimatedPressable onPress={onSeeAll} accessibilityRole="button" accessibilityLabel="See all items">
          <Text style={styles.seeAll}>See all →</Text>
        </AnimatedPressable>
      </View>

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
                <Image source={{ uri: it.image_url }} style={styles.art} resizeMode="contain" accessibilityIgnoresInvertColors />
              ) : (
                <View style={[styles.art, styles.artEmpty, { backgroundColor: accentColor + '12' }]}>
                  <Ionicons name="cube-outline" size={26} color={accentColor} />
                  {/* No catalog art yet — user photos will fill these as the
                      database grows; say so instead of looking broken. */}
                  <Text style={styles.comingSoon}>Image coming soon</Text>
                </View>
              )}
              <View style={styles.meta}>
                <Text style={[styles.nm, { color: colors.text }]} numberOfLines={2}>{cleanCatalogTitle(it.title, { brand: it.brand, setCode: it.set_code })}</Text>
                {fmtPrice(it.estimated_price) ? (
                  <Text style={styles.pr}>{fmtPrice(it.estimated_price)}</Text>
                ) : (
                  <Text style={[styles.tag, { color: colors.muted }]}>{it.rarity || it.set_code || 'Explore'}</Text>
                )}
              </View>
            </AnimatedPressable>
          ))}
          {/* See-all tile — light tiffany wash + dashed border (mockup) */}
          <AnimatedPressable
            style={[styles.card, styles.seeAllTile]}
            onPress={onSeeAll}
            accessibilityRole="button"
            accessibilityLabel="See all items"
          >
            <Text style={styles.seeAllTileText}>
              See all{total ? `\n${total.toLocaleString()}` : ''} →
            </Text>
          </AnimatedPressable>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  // Mockup `.sec` with tiffany border: white card framing the one rail.
  wrap: {
    marginBottom: 18,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: tokens.brand.base,
    paddingVertical: 12,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, marginBottom: 10 },
  // Mockup `.lbl`: 11/800, letter-spaced, muted.
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.4, flex: 1, marginRight: 8 },
  seeAll: { fontSize: 13, fontWeight: '600', color: tokens.brand.deep },
  rail: { gap: 12, paddingHorizontal: 12, paddingBottom: 4 },
  card: { width: 140, borderRadius: 14, borderWidth: 1, overflow: 'hidden' },
  // Full card at the standard 63:88 ratio + `contain` so the whole card shows
  // (was height:120 + cover, which sliced the name/HP off the top & bottom).
  // The faint tint fills the gutters for non-portrait cards.
  art: { width: '100%', aspectRatio: 63 / 88, backgroundColor: tokens.brand.base + '0A' },
  artEmpty: { alignItems: 'center', justifyContent: 'center' },
  comingSoon: { fontSize: 10, fontWeight: '600', marginTop: 6, color: tokens.brand.deep, opacity: 0.7 },
  meta: { paddingVertical: 8, paddingHorizontal: 10 },
  nm: { fontSize: 12, fontWeight: '700' },
  // Mockup `.pr`: deep tiffany — holds contrast on white where base washes out.
  pr: { fontSize: 15, fontWeight: '900', marginTop: 2, color: tokens.brand.deep },
  tag: { fontSize: 9, marginTop: 2 },
  seeAllTile: {
    width: 110,
    alignItems: 'center',
    justifyContent: 'center',
    borderStyle: 'dashed',
    borderColor: tokens.brand.base,
    backgroundColor: '#81D8D012',
  },
  seeAllTileText: { fontSize: 13, fontWeight: '700', textAlign: 'center', color: tokens.brand.deep },
  empty: { fontSize: 13, paddingHorizontal: 12, paddingVertical: 12 },
});

export default React.memo(CategoryOverviewRail);
