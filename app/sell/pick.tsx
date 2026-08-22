/**
 * Pick an item from your collection to sell.
 *
 * WHY THIS SCREEN EXISTS
 *
 * The marketplace's "Sell" button offered "From my collection" and then pushed
 * `/(tabs)/items` — the plain collection tab, carrying no intent whatsoever. The
 * user had asked to sell something and got dropped into a browse screen with no
 * instruction, no sell mode, and nothing marking which tap would do the thing
 * they came for.
 *
 * Opening an item did not rescue it either: the sell entry point on the item
 * screen was `SellOnSparrowSection`, rendered far below the fold under Add
 * Photo, Edit/Share, Item Details and several more sections. So the flow read
 * as a dead end — reported 2026-08-08 as "there is no button from that workflow
 * to then select an item", which is exactly right.
 *
 * (That section was REMOVED on 2026-08-22: Sell is now a top-row action on the
 * item screen and opens app/sell/new directly. This screen is unaffected — it
 * answers the "start from selling, pick an item" direction, which the item
 * screen cannot.)
 *
 * A promise of "select an item from your collection" has to be answered by a
 * screen where selecting an item is the ONLY thing to do. That is this.
 *
 * ── What it deliberately does NOT show ──────────────────────────────────────
 * Whether the item can reach Target Hit. That depends on `canonical_key`, which
 * is not in `ITEMS_SELECT` — and widening the app's hottest read (guarded by its
 * own contract test, `npm run verify:items-contract`) to decorate a picker is
 * not a proportionate trade for a screen you leave in one tap.
 *
 * The seller is not left guessing: app/sell/new.tsx runs the catalogue match and
 * says plainly, before listing, whether members watching will be alerted. The
 * information arrives one screen later, where it is actionable, instead of here
 * where it is not.
 */
import React, { useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, ActivityIndicator } from 'react-native';
import { Image } from 'expo-image';
import { useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAsync } from '@/hooks/useAsync';
import { useSettings } from '@/lib/settings';
import { dataProvider, type Item } from '@/data';
import { formatPrice } from '@/lib/format';
import { CATEGORY_SLUG_TO_NAME } from '@/constants/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

function SellPickScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  // A seller with a big collection still only lists one thing at a time, so a
  // single generous page beats pagination plumbing on a screen you leave
  // immediately.
  const { data: items, loading, error, retry } = useAsync(
    async () => dataProvider.listItems({ limit: 200, offset: 0 }),
    [],
  );

  const pick = useCallback((item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Hands off to the SAME composer the free-text route uses, with the item's
    // id. One compose screen for both routes — two would drift, and this one
    // already handles the photo, the consent checkbox and the reach notice.
    //
    // The id alone used to be all that travelled, so the composer opened blank:
    // no photo, no name, no price, nothing showing WHICH item was picked. The
    // seller had already given that information once when they added the item,
    // and the screen asked for it again (reported 2026-08-09 as "double work
    // and not useful").
    //
    // These extra params are a SEED for the editable fields plus the summary
    // that proves the selection carried. They are not the source of truth:
    // `POST /p2p/listings` still derives name, category and canonical_key from
    // `item_id` server-side, so a stale or tampered param cannot change what
    // gets listed. Everything here is already in hand from `listItems` — no
    // extra fetch, and no widening of ITEMS_SELECT (see this file's header).
    router.push({
      pathname: '/sell/new',
      params: {
        itemId: item.id,
        itemName: item.name,
        itemCategory: item.category ?? '',
        itemImage: item.imageUrl ?? '',
        // Only a usable price seeds the box. `0` is the unpriced case (a
        // category with no sold-comp source), and a prefilled 0 would both read
        // as "worthless" and fail the server's `price > 0` on submit.
        itemValue: item.price > 0 ? String(Math.round(item.price * 100) / 100) : '',
        itemCondition: item.condition ?? '',
      },
    } as Href);
  }, [router, settings.hapticsEnabled]);

  const renderItem = useCallback(({ item }: { item: Item }) => {
    return (
      <AnimatedPressable
        onPress={() => pick(item)}
        style={[styles.row, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel={`Sell ${item.name}`}
      >
        {item.imageUrl ? (
          <Image source={{ uri: item.imageUrl }} style={styles.thumb} contentFit="cover" transition={120} />
        ) : (
          <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.accent + '12' }]}>
            <Ionicons name="image-outline" size={20} color={colors.muted} />
          </View>
        )}
        <View style={styles.rowBody}>
          <Text style={[styles.rowTitle, { color: colors.text }]} numberOfLines={1}>{item.name}</Text>
          <Text style={[styles.rowMeta, { color: colors.muted }]} numberOfLines={1}>
            {[
              item.category ? (CATEGORY_SLUG_TO_NAME[item.category] ?? item.category) : null,
              item.price ? formatPrice(item.price, settings.currency, settings.numberLocale) : null,
            ].filter(Boolean).join(' · ')}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.muted} />
      </AnimatedPressable>
    );
  }, [colors, pick, settings.currency, settings.numberLocale]);

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Choose an item" />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : error ? (
        // FAILED is not EMPTY. Telling a seller their collection is empty when
        // the read failed sends them to the wrong route entirely.
        <EmptyState
          icon="cloud-offline-outline"
          title="Couldn't load your collection"
          subtitle="Your items are safe — we just couldn't reach them."
          colors={colors}
          action={
            <AnimatedPressable
              onPress={retry}
              style={[styles.cta, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Try again"
            >
              <Text style={[styles.ctaText, { color: colors.accentText }]}>Try again</Text>
            </AnimatedPressable>
          }
        />
      ) : (
        <FlatList
          data={items ?? []}
          keyExtractor={(i) => i.id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            <Text style={[styles.hint, { color: colors.muted }]}>
              Pick what you want to sell. You&apos;ll set the price next.
            </Text>
          }
          ListEmptyComponent={
            // The genuinely-empty case has a real answer: the marketplace-only
            // route exists precisely so an empty collection is not a dead end
            // (spec §5c).
            <EmptyState
              icon="cube-outline"
              title="Nothing in your collection yet"
              subtitle="You can still sell — just describe what you have."
              colors={colors}
              action={
                <AnimatedPressable
                  onPress={() => router.replace('/sell/new' as Href)}
                  style={[styles.cta, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Sell something not in my collection"
                >
                  <Text style={[styles.ctaText, { color: colors.accentText }]}>
                    Sell something else
                  </Text>
                </AnimatedPressable>
              }
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: 16, gap: 10, paddingBottom: 48 },
  hint: { fontSize: textToken.sm, marginBottom: 6 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, padding: 10,
  },
  thumb: { width: 52, height: 52, borderRadius: radius.sm },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  rowBody: { flex: 1, gap: 2 },
  rowTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  rowMeta: { fontSize: textToken.xs },
  cta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 12, paddingHorizontal: 20, borderRadius: radius.pill,
  },
  ctaText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
});

export default function SellPickScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sell — choose item">
      <SellPickScreen />
    </ScreenErrorBoundary>
  );
}
