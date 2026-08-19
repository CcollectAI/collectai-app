/**
 * YourItemsRail — what YOU own in this category, in the same carousel as the
 * catalog rail beside it.
 *
 * WHY THIS IS A DELIBERATE REVERSAL
 * `app/categories/[categoryId].tsx`'s header lists "Items-in-Category" among
 * the sections removed in the 2026-08-11 museum redesign, which collapsed a
 * pile of carousels into ONE that funnels every tap toward an affiliate buy.
 * That reasoning was about the CATALOG rails — five different views of "what
 * exists" competing with each other. Your own collection is a different
 * question: the catalog answers "what is out there", this answers "what do I
 * already have", and the second is the one a collector opens the app for.
 * Requested directly, 2026-08-19.
 *
 * It is the THIRD rail, not a replacement, and it is placed FIRST — your
 * shelf before the shop.
 *
 * WHY IT LOOKS IDENTICAL TO CategoryOverviewRail
 * Same card width, same 63:88 art ratio, same `.lbl` header, same tiffany
 * frame. Two rails on one screen that scroll the same way must LOOK the same
 * way, or the difference reads as an accident. The one intentional divergence:
 * a tap here opens YOUR item (`/item/[id]`), not the catalog museum, because
 * these are rows you own.
 *
 * VALUES COME FROM `listItems`, WHICH IS THE POINT
 * `categoryProvider.getCategoryStore` already selects exactly this set on every
 * category open — and its mapper hardcodes `price: 0`, so rendering that would
 * have priced your whole shelf at zero (unknown-as-zero, the house bug class).
 * This reads through `dataProvider.listItems({ category })`, so the price on a
 * card here is the same number the Items tab and the portfolio total show,
 * from the one `mapItemRow` call site the value gate enforces.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, Image, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable } from '@/motion';
import { dataProvider } from '@/data';
import { formatPrice, isUnpriced, UNPRICED_LABEL } from '@/lib/format';
import { colors as tokens } from '@/theme/tokens';
import logger from '@/utils/logger';
import type { Item } from '@/data/types';
import type { AppTheme } from '@/hooks/useAppTheme';

/** Matches CategoryOverviewRail's page size, so the two rails feel the same. */
const RAIL_LIMIT = 20;

type Props = {
  /** Category SLUG ('mtg') — the same value `items.category` stores. */
  categoryId: string;
  accentColor: string;
  colors: AppTheme['colors'];
  onItemPress: (item: Item) => void;
  onSeeAll: () => void;
};

function YourItemsRail({ categoryId, accentColor, colors, onItemPress, onSeeAll }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  // A failed read must NOT render as "you own none of these". Same distinction
  // CategoryOverviewRail draws, and for the same reason: `[]` from a catch is
  // indistinguishable from an empty shelf, and one of them is a lie about the
  // user's own collection.
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    dataProvider
      .listItems({ category: categoryId, limit: RAIL_LIMIT })
      .then((rows) => {
        if (cancelled) return;
        setItems(rows);
        setLoading(false);
      })
      .catch((e) => {
        // logger.error, not warn — warn is stripped in release builds, so this
        // would be invisible on exactly the builds where it matters.
        logger.error('[YourItemsRail] fetch failed:', e);
        if (cancelled) return;
        setFailed(true);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [categoryId, reloadKey]);

  // `isUnpriced`, not a hand-rolled `p > 0`. An unpriced item is not a
  // zero-euro item — `formatPrice(0)` prints "EUR 0.00" as a confident claim
  // about something never valued — and that rule already has ONE definition
  // (src/lib/format.ts, UNPRICED_LABEL). A second copy here would be the
  // second definition that drifts.
  const priceOf = useCallback(
    (p: number | null | undefined) => (isUnpriced(p) ? null : formatPrice(p as number)),
    [],
  );

  // Nothing owned in this category is not a problem to report — it is the
  // normal state for 50-odd categories. Render NOTHING rather than an empty
  // frame, which would read as a component that failed to load
  // (ui-playbook: "an always-rendered card is an empty grey box").
  if (!loading && !failed && items.length === 0) return null;

  return (
    <View style={[styles.wrap, { backgroundColor: colors.card }]}>
      <View style={styles.head}>
        <Text style={[styles.label, { color: colors.muted }]} numberOfLines={1}>
          🧳 YOUR COLLECTION
        </Text>
        {items.length > 0 ? (
          <AnimatedPressable
            onPress={onSeeAll}
            accessibilityRole="button"
            accessibilityLabel="See all of your items in this category"
          >
            <Text style={styles.seeAll}>See all →</Text>
          </AnimatedPressable>
        ) : null}
      </View>

      {loading ? (
        <ActivityIndicator color={accentColor} style={{ marginVertical: 28 }} />
      ) : failed ? (
        <AnimatedPressable
          onPress={() => setReloadKey((k) => k + 1)}
          accessibilityRole="button"
          accessibilityLabel="Retry loading your items"
          style={styles.retry}
        >
          <Ionicons name="refresh-outline" size={16} color={accentColor} />
          <Text style={[styles.retryText, { color: accentColor }]}>Couldn&apos;t load — tap to retry</Text>
        </AnimatedPressable>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.rail}>
          {items.map((it) => (
            <AnimatedPressable
              key={it.id}
              style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => onItemPress(it)}
              accessibilityRole="button"
              accessibilityLabel={
                `${it.name}${priceOf(it.price) ? `, ${priceOf(it.price)}` : `, ${UNPRICED_LABEL}`}. Opens your item`
              }
            >
              {it.imageUrl ? (
                <Image
                  source={{ uri: it.imageUrl }}
                  style={styles.art}
                  resizeMode="contain"
                  accessibilityIgnoresInvertColors
                />
              ) : (
                <View style={[styles.art, styles.artEmpty, { backgroundColor: accentColor + '12' }]}>
                  <Ionicons name="image-outline" size={26} color={accentColor} />
                  <Text style={styles.noPhoto}>No photo yet</Text>
                </View>
              )}
              <View style={styles.meta}>
                <Text style={[styles.nm, { color: colors.text }]} numberOfLines={2}>{it.name}</Text>
                {priceOf(it.price) ? (
                  <Text style={styles.pr}>{priceOf(it.price)}</Text>
                ) : (
                  <Text style={[styles.tag, { color: colors.muted }]} numberOfLines={2}>
                    {UNPRICED_LABEL}
                  </Text>
                )}
              </View>
            </AnimatedPressable>
          ))}
          {/* Deliberately NO count on this tile. The rail is capped at
              RAIL_LIMIT and the read does not return a total, so "See all 20"
              would state a cap as if it were the size of your collection —
              a capped aggregate presented as the whole truth. */}
          <AnimatedPressable
            style={[styles.card, styles.seeAllTile]}
            onPress={onSeeAll}
            accessibilityRole="button"
            accessibilityLabel="See all of your items in this category"
          >
            <Text style={styles.seeAllTileText}>See all →</Text>
          </AnimatedPressable>
        </ScrollView>
      )}
    </View>
  );
}

// Copied deliberately from CategoryOverviewRail rather than re-derived: two
// rails that scroll the same way on one screen must measure the same, and a
// second set of hand-tuned numbers drifts from the first on the next tweak.
const styles = StyleSheet.create({
  wrap: {
    marginBottom: 18,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: tokens.brand.base,
    paddingVertical: 12,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, marginBottom: 10 },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.4, flex: 1, marginRight: 8 },
  seeAll: { fontSize: 13, fontWeight: '600', color: tokens.brand.deep },
  rail: { gap: 12, paddingHorizontal: 12, paddingBottom: 4 },
  card: { width: 140, borderRadius: 14, borderWidth: 1, overflow: 'hidden' },
  art: { width: '100%', aspectRatio: 63 / 88, backgroundColor: tokens.brand.base + '0A' },
  artEmpty: { alignItems: 'center', justifyContent: 'center' },
  noPhoto: { fontSize: 11, fontWeight: '600', marginTop: 6, color: tokens.brand.deep, opacity: 0.7 },
  meta: { paddingVertical: 8, paddingHorizontal: 10 },
  nm: { fontSize: 12, fontWeight: '700' },
  pr: { fontSize: 15, fontWeight: '900', marginTop: 2, color: tokens.brand.deep },
  // 11, NOT the sibling rail's 9. Copying the neighbour is right for layout and
  // wrong for type: docs/ui-playbook.md bans 10pt for anything a user reads and
  // 9 is worse — `app/listings.tsx` had its 9/10/11 literals closed out for
  // exactly this. This label carries a real sentence ("Cannot estimate value"),
  // so it is text, not a glyph. The 2pt divergence from CategoryOverviewRail is
  // deliberate; that rail's own 9pt is a pre-existing item, not a precedent.
  tag: { fontSize: 11, lineHeight: 15, marginTop: 2 },
  seeAllTile: {
    width: 110,
    alignItems: 'center',
    justifyContent: 'center',
    borderStyle: 'dashed',
    borderColor: tokens.brand.base,
    backgroundColor: '#81D8D012',
  },
  seeAllTileText: { fontSize: 13, fontWeight: '700', textAlign: 'center', color: tokens.brand.deep },
  retry: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 20, justifyContent: 'center' },
  retryText: { fontSize: 13, fontWeight: '600' },
});

export default React.memo(YourItemsRail);
