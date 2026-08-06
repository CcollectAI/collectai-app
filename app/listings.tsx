/**
 * Member Marketplace — browse listings from other collectors.
 *
 * See docs/P2P_MARKETPLACE_SPEC.md. Stage 1: listings only, no payments.
 *
 * Why a dedicated screen rather than a section inside app/(tabs)/marketplace.tsx:
 * that file is 1,266 lines, still carries the ExternalTabBar overlap bug
 * (paddingBottom: 32 where 68-92 is needed) and its main feature is disabled
 * pre-launch. Adding a grid there means inheriting its problems. A full screen
 * is also the more honest signal to a seller that selling actually happens here
 * — a cramped section reads as an afterthought, and sellers list where they
 * believe buyers are.
 *
 * Three playbook rules this screen is built around (docs/ui-playbook.md):
 *
 * 1. **The header is OUTSIDE the list.** FlashList v2 absolutely-positions
 *    every cell including ListHeaderComponent; a tall header overflows its
 *    measured container and iOS stops hit-testing it — visible and completely
 *    dead. The search box and filter chips here would hit exactly that, so
 *    they live above the list, and the list is a FlatList regardless.
 * 2. **Bottom inset via useTabBarInset.** QuickNavBar is absolute and reserves
 *    no space (58 + safe-area, same geometry as ExternalTabBar). Without this
 *    the last row of the grid sits under it.
 * 3. **No `accessibilityRole="tabbar"`** anywhere — it hard-crashes Android.
 */
import React, { useCallback, useMemo, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  StyleSheet,
  RefreshControl,
  Animated,
} from 'react-native';
import { Image } from 'expo-image';
import { useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { useAsync } from '@/hooks/useAsync';
import { useSettings, type NumberLocale } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { collectorsApi } from '@/api/collectorsApi';
import type { P2PListing } from '@/api/p2pApi';
import type { CurrencyCode } from '@/data/types';
import { CATEGORIES as ALL_CATS, CATEGORY_SLUG_TO_NAME } from '@/constants/categories';
import { radius, text as textToken, fontWeight, shadow } from '@/theme/tokens';
import logger from '@/utils/logger';

const NUM_COLUMNS = 2;

/** Categories offered as filter chips. Slugs, not display names — the column
 *  stores slugs and a display-name filter would silently match nothing
 *  (learning_join_vocabulary_slug_vs_display_name). */
const FILTER_SLUGS = ALL_CATS.slice(0, 12).map((c) => c.slug);

function ListingCard({
  listing,
  onPress,
  currency,
  numberLocale,
}: {
  listing: P2PListing;
  onPress: () => void;
  currency: CurrencyCode;
  numberLocale?: NumberLocale;
}) {
  const { colors } = useAppTheme();
  return (
    <AnimatedPressable
      onPress={onPress}
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`${listing.title}, ${formatPrice(listing.price, currency, numberLocale)}`}
    >
      {listing.image_url ? (
        <View>
          <Image
            source={{ uri: listing.image_url }}
            style={styles.thumb}
            contentFit="cover"
            transition={150}
          />
          {/* Never let a catalog scan read as the seller's own photo — a
              second-hand buyer judges condition from the picture. */}
          {/* A seller's grid mixes live and sold items; identical tiles make
              it unreadable. Dim + label anything not active. */}
          {listing.status !== 'active' ? (
            <View style={styles.soldOverlay}>
              <View style={[styles.soldPill, { backgroundColor: colors.text + 'E0' }]}>
                <Text style={[styles.soldPillText, { color: colors.background }]}>
                  {listing.status === 'sold' ? 'Sold' : 'Removed'}
                </Text>
              </View>
            </View>
          ) : null}
          {listing.image_is_catalog ? (
            <View style={[styles.stockTag, { backgroundColor: colors.background + 'E6' }]}>
              <Text style={[styles.stockTagText, { color: colors.muted }]}>Catalog photo</Text>
            </View>
          ) : null}
        </View>
      ) : (
        // Never a blank box: an empty tile reads as a broken image. A tinted
        // placeholder with the category glyph keeps the grid rhythm intact.
        <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.accent + '12' }]}>
          <Ionicons name="image-outline" size={26} color={colors.muted} />
        </View>
      )}
      <View style={styles.cardBody}>
        <Text style={[styles.cardTitle, { color: colors.text }]} numberOfLines={2}>
          {listing.title}
        </Text>
        <Text style={[styles.cardPrice, { color: colors.text }]}>
          {formatPrice(listing.price, currency, numberLocale)}
        </Text>
        <View style={styles.cardMetaRow}>
          {listing.condition_label ? (
            <Text style={[styles.cardMeta, { color: colors.muted }]} numberOfLines={1}>
              {listing.condition_label}
            </Text>
          ) : null}
          {listing.is_mine ? (
            <View style={[styles.youPill, { backgroundColor: colors.accent + '1E' }]}>
              <Text style={[styles.youPillText, { color: colors.accent }]}>You</Text>
            </View>
          ) : null}
        </View>
      </View>
    </AnimatedPressable>
  );
}

function MemberMarketplaceScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const bottomInset = useTabBarInset();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  // Seller view. Without this a seller lists something and then cannot find
  // it — the API had a `mine` filter with no way to reach it.
  const [mineOnly, setMineOnly] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const { data, loading, error, retry } = useAsync(
    async () => {
      const res = await collectorsApi.listP2PListings({
        category: activeCategory ?? undefined,
        mine: mineOnly || undefined,
        limit: 50,
      });
      return res?.listings ?? [];
    },
    [activeCategory, mineOnly],
  );

  // Client-side title filter. Deliberately NOT a server round-trip: the result
  // set is capped at 50, so filtering locally is instant and avoids a request
  // per keystroke. Revisit when a listing count makes paging necessary.
  const listings = useMemo(() => {
    const all = data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter((l) => l.title.toLowerCase().includes(q));
  }, [data, query]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await retry();
    } catch (e) {
      logger.error('[listings] refresh failed:', e);
    } finally {
      setRefreshing(false);
    }
  }, [retry]);

  const openListing = useCallback(
    (id: string) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      // `as Href` because .expo/types/router.d.ts is generated by Expo and
      // does not know this route until the dev server regenerates it. Same
      // pattern as src/screens/Settings.tsx for /my-suggestions. The route IS
      // registered in app/_layout.tsx.
      router.push({ pathname: '/listing/[id]', params: { id } } as unknown as Href);
    },
    [router, settings.hapticsEnabled],
  );

  const renderItem = useCallback(
    ({ item }: { item: P2PListing }) => (
      <ListingCard
        listing={item}
        currency={settings.currency}
        numberLocale={settings.numberLocale}
        onPress={() => openListing(item.id)}
      />
    ),
    [openListing, settings.currency, settings.numberLocale],
  );

  return (
    // Plain View, NOT SafeAreaView: ScreenHeader already applies
    // `insets.top` (ScreenHeader.tsx:43). Wrapping in SafeAreaView too would
    // double-pad the top — the playbook's SafeAreaView rule is for screens
    // WITHOUT this header.
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Marketplace" />

      {/* Search + filters live OUTSIDE the list — see the file header.
          Animated.View carries the enter-reveal the playbook checklist
          requires; the list itself is not wrapped, so its virtualisation and
          scroll performance are untouched. */}
      <Animated.View style={[styles.controls, animatedStyle]}>
        {/* Offers inbox. Sits above the browse/mine split because an
            outstanding offer is time-sensitive in a way browsing is not — a
            seller who misses one loses the sale. */}
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/offers' as Href);
          }}
          style={[styles.offersRow, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel="View your offers"
        >
          <Ionicons name="swap-horizontal-outline" size={16} color={colors.accent} />
          <Text style={[styles.offersText, { color: colors.text }]}>Your offers</Text>
          <Ionicons name="chevron-forward" size={14} color={colors.muted} />
        </AnimatedPressable>

        {/* Browse vs My listings. A segmented control rather than a filter
            chip: these are two different jobs (find something to buy vs
            manage what I sell), and burying "mine" among category chips
            makes a seller hunt for their own inventory. */}
        <View style={[styles.segment, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {[false, true].map((isMine) => {
            const active = mineOnly === isMine;
            return (
              <AnimatedPressable
                key={String(isMine)}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  setMineOnly(isMine);
                }}
                style={[styles.segmentBtn, active && { backgroundColor: colors.accent + '1E' }]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={isMine ? 'My listings' : 'Browse all listings'}
              >
                <Text
                  style={[
                    styles.segmentText,
                    { color: active ? colors.accent : colors.muted },
                    active && { fontWeight: fontWeight.bold },
                  ]}
                >
                  {isMine ? 'My listings' : 'Browse'}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>

        <View style={[styles.searchBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="search" size={16} color={colors.muted} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            value={query}
            onChangeText={setQuery}
            placeholder="Search member listings"
            placeholderTextColor={colors.muted}
            returnKeyType="search"
            accessibilityLabel="Search member listings"
          />
          {query.length > 0 ? (
            <AnimatedPressable
              onPress={() => setQuery('')}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel="Clear search"
            >
              <Ionicons name="close-circle" size={16} color={colors.muted} />
            </AnimatedPressable>
          ) : null}
        </View>

        <FlatList
          horizontal
          data={[null, ...FILTER_SLUGS]}
          keyExtractor={(slug, i) => slug ?? `all-${i}`}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
          renderItem={({ item: slug }) => {
            const active = activeCategory === slug;
            return (
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  setActiveCategory(slug);
                }}
                style={[
                  styles.chip,
                  { borderColor: colors.border, backgroundColor: colors.card },
                  active && { backgroundColor: colors.accent + '1E', borderColor: colors.accent },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={slug ? CATEGORY_SLUG_TO_NAME[slug] ?? slug : 'All categories'}
              >
                <Text
                  style={[
                    styles.chipText,
                    { color: active ? colors.accent : colors.muted },
                    active && { fontWeight: fontWeight.bold },
                  ]}
                >
                  {slug ? CATEGORY_SLUG_TO_NAME[slug] ?? slug : 'All'}
                </Text>
              </AnimatedPressable>
            );
          }}
        />
      </Animated.View>

      {/* Result count: cheap orientation, and it makes a filter that matched
          nothing obvious before the user scrolls. */}
      {!loading && !error && listings.length > 0 ? (
        <Text style={[styles.resultCount, { color: colors.muted }]}>
          {listings.length} {mineOnly ? 'of your listings' : `listing${listings.length === 1 ? '' : 's'}`}
          {activeCategory ? ` in ${CATEGORY_SLUG_TO_NAME[activeCategory] ?? activeCategory}` : ''}
        </Text>
      ) : null}

      {loading && !refreshing ? (
        // Grid-shaped skeleton, not SkeletonList's rows. A list-shaped
        // placeholder that snaps into a 2-column grid is a visible layout
        // jolt — the skeleton's job is to hold the shape the content will
        // take, otherwise it adds a flicker instead of hiding one.
        <View style={styles.skeletonWrap}>
          {[0, 1, 2, 3].map((i) => (
            <View
              key={i}
              style={[styles.skeletonCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            >
              <View style={[styles.skeletonThumb, { backgroundColor: colors.border + '55' }]} />
              <View style={styles.skeletonBody}>
                <View style={[styles.skeletonLine, { backgroundColor: colors.border + '55' }]} />
                <View style={[styles.skeletonLineShort, { backgroundColor: colors.border + '55' }]} />
              </View>
            </View>
          ))}
        </View>
      ) : error ? (
        <EmptyState
          icon="cloud-offline-outline"
          title="Couldn't load listings"
          subtitle="Check your connection and try again."
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
          data={listings}
          keyExtractor={(l) => l.id}
          renderItem={renderItem}
          numColumns={NUM_COLUMNS}
          columnWrapperStyle={styles.column}
          // QuickNavBar is absolute and reserves no layout space.
          contentContainerStyle={[styles.list, { paddingBottom: bottomInset }]}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />
          }
          ListEmptyComponent={
            // Demand-aware, not apologetic. "No listings yet" tells a seller
            // nothing happens here; naming the waiting demand is the strongest
            // seller-acquisition line we have, and it is the one thing a
            // generic marketplace cannot say (docs/P2P_MARKETPLACE_SPEC.md).
            <View style={styles.empty}>
              <Ionicons name="pricetags-outline" size={44} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                {mineOnly
                  ? 'You have no listings yet'
                  : query || activeCategory
                    ? 'Nothing matches that yet'
                    : 'Be the first to list'}
              </Text>
              <Text style={[styles.emptyBody, { color: colors.muted }]}>
                {mineOnly
                  ? 'Open any item in your collection and tap Sell this. It appears here straight away.'
                  : query || activeCategory
                  ? 'Try another category, or clear the search.'
                  : 'Members set target prices on the things they want. List an item you own and they get alerted the moment it matches — open any item in your collection and tap Sell this.'}
              </Text>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push('/(tabs)/items');
                }}
                style={[styles.cta, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Choose an item from your collection to sell"
              >
                <Text style={[styles.ctaText, { color: colors.accentText }]}>
                  Choose an item to sell
                </Text>
              </AnimatedPressable>
            </View>
          }
          ListFooterComponent={
            listings.length > 0 ? (
              <View style={styles.footerWrap}>
                <Text style={[styles.footerNote, { color: colors.muted }]}>
                  Buyers and sellers arrange payment and delivery between themselves.
                  Sparrow doesn&apos;t handle payment and there is no buyer protection.
                </Text>
                <AnimatedPressable
                  onPress={() => router.push('/legal/marketplace-terms' as Href)}
                  accessibilityRole="link"
                  accessibilityLabel="Read the marketplace terms"
                >
                  <Text style={[styles.footerLink, { color: colors.accent }]}>Marketplace terms</Text>
                </AnimatedPressable>
              </View>
            ) : null
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

export default function MemberMarketplaceScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Member Marketplace">
      <MemberMarketplaceScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  pad: { paddingHorizontal: 16, paddingTop: 12 },
  controls: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 },
  offersRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md,
    paddingHorizontal: 12, paddingVertical: 10, marginBottom: 10,
  },
  offersText: { flex: 1, fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  segment: {
    flexDirection: 'row', borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill, padding: 3, marginBottom: 10,
  },
  segmentBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 7, borderRadius: radius.pill,
  },
  segmentText: { fontSize: textToken.sm },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 10,
    ...shadow.card,
  },
  searchInput: { flex: 1, fontSize: textToken.md, padding: 0 },
  chipRow: { gap: 8, paddingVertical: 10, paddingRight: 8 },
  chip: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    // 7pt vertical + 12pt text = ~34pt; with the 10pt row padding the tap
    // target clears the 44pt minimum without making the row look chunky.
    paddingVertical: 7,
  },
  chipText: { fontSize: textToken.sm },
  skeletonWrap: {
    flexDirection: 'row', flexWrap: 'wrap',
    paddingHorizontal: 16, gap: 12,
  },
  skeletonCard: {
    width: '47%', borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md, overflow: 'hidden', marginBottom: 14,
  },
  skeletonThumb: { width: '100%', aspectRatio: 4 / 5 },
  skeletonBody: { padding: 11, gap: 7 },
  skeletonLine: { height: 10, borderRadius: 4, width: '85%' },
  skeletonLineShort: { height: 13, borderRadius: 4, width: '55%' },
  resultCount: { fontSize: textToken.xs, paddingHorizontal: 16, paddingBottom: 6 },
  list: { paddingHorizontal: 16, paddingTop: 2 },
  column: { gap: 12 },
  // Elevation over a hairline border: a flat outlined tile reads as a
  // placeholder, a lifted one reads as a product. shadow.card is the repo's
  // existing token, so this matches every other surface rather than inventing
  // a new depth.
  card: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    overflow: 'hidden',
    marginBottom: 14,
    ...shadow.card,
  },
  // 4:5, not 1:1. Collectibles are mostly portrait (cards ~5:7, figures tall)
  // and a square crop decapitates them. 4:5 is what Vinted/Depop use for mixed
  // inventory — tall enough to show the object, short enough to fit two rows
  // on screen.
  thumb: { width: '100%', aspectRatio: 4 / 5 },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  soldOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.42)',
  },
  soldPill: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: radius.pill },
  soldPillText: { fontSize: textToken.xs, fontWeight: fontWeight.bold, letterSpacing: 0.4 },
  stockTag: {
    position: 'absolute', left: 6, bottom: 6,
    paddingHorizontal: 6, paddingVertical: 3, borderRadius: radius.xs,
  },
  stockTagText: { fontSize: 9, fontWeight: fontWeight.semibold },
  cardBody: { padding: 11, gap: 4 },
  // Title is secondary to price: a buyer scanning a grid decides on price
  // first, then reads the name to confirm. Muted-weight title, heavy price.
  cardTitle: { fontSize: textToken.sm, fontWeight: fontWeight.medium, lineHeight: 16 },
  cardPrice: { fontSize: textToken.lg, fontWeight: fontWeight.extrabold, letterSpacing: -0.3 },
  cardMetaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 },
  cardMeta: { fontSize: textToken.xs, flexShrink: 1, letterSpacing: 0.2 },
  youPill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: radius.xs },
  youPillText: { fontSize: textToken.xs, fontWeight: fontWeight.bold },
  empty: { alignItems: 'center', paddingHorizontal: 32, paddingTop: 56, gap: 10 },
  emptyTitle: { fontSize: textToken.lg, fontWeight: fontWeight.bold, textAlign: 'center' },
  emptyBody: { fontSize: textToken.sm, textAlign: 'center', lineHeight: 19 },
  cta: { marginTop: 8, paddingHorizontal: 20, paddingVertical: 11, borderRadius: radius.md },
  ctaText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  footerWrap: { alignItems: 'center', paddingBottom: 8 },
  footerLink: { fontSize: textToken.xs, fontWeight: fontWeight.bold, paddingVertical: 8 },
  footerNote: {
    fontSize: textToken.xs, textAlign: 'center',
    paddingVertical: 20, paddingHorizontal: 24, lineHeight: 16,
  },
});
