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
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  StyleSheet,
  RefreshControl,
  Animated,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Image } from 'expo-image';
import { useRouter, type Href } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { FilterSheet, type FilterConfig } from '@/components/FilterSheet';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { useSettings, type NumberLocale, type Settings } from '@/lib/settings';
import { convertCurrency } from '@/lib/fx';
import { formatPrice, getCurrencySymbol } from '@/lib/format';
import { timeAgoShort } from '@/lib/timeAgo';
import { collectorsApi } from '@/api/collectorsApi';
import {
  countOffersNeedingAction,
  type P2PListing,
  type P2PSort,
  type P2PCategoryFacet,
} from '@/api/p2pApi';
import type { CurrencyCode } from '@/data/types';
import { CATEGORY_SLUG_TO_NAME } from '@/constants/categories';
import { radius, text as textToken, fontWeight, shadow } from '@/theme/tokens';
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

const NUM_COLUMNS = 2;

/** 12 rows of a 2-column grid. Divisible by NUM_COLUMNS so a full page never
 *  leaves a half-filled last row mid-list, which reads as the end of the data. */
const PAGE_SIZE = 24;

// The filter chips are no longer a static list of all app categories — they
// come from /p2p/facets/categories, so only categories with live listings are
// offered. See `filterCategories` below. The chip VALUE is still the slug, never
// the display name (learning_join_vocabulary_slug_vs_display_name); only the
// label is humanised, and it now carries the listing count.

/** Pseudo-"condition" carrying the only-my-listings toggle into the shared
 *  FilterSheet. See the onApply comment for why it is not a new field. */
const MINE_FILTER = 'Only my listings';

/** Heading for that section. The sheet's default is "Condition", which would
 *  file "Only my listings" under a label it has nothing to do with — nobody
 *  hunting for their own inventory opens a Condition dropdown. */
const MINE_SECTION_TITLE = 'Show';

/** Dismissed-explainer flag. Persisted so the intro appears once, not on every
 *  visit — a banner that never goes away stops being information and becomes
 *  furniture the user scrolls past. */
const INTRO_DISMISSED_KEY = '@sparrowcollect/marketplace_intro_dismissed';

/** The sheet defaults to six sort keys; the marketplace API supports three, so
 *  we narrow the list rather than accept all six and quietly fold four of them
 *  onto 'newest'. That folding is what makes a sheet show "Name (A → Z)" as
 *  the live selection while the server returns newest-first — the mapping is
 *  now a bijection, so what the sheet says is what the list does.
 *
 *  Labels say "Price", not the default "Value": these are asking prices set by
 *  a seller, not our valuation of the item, and conflating the two in a
 *  marketplace is a claim we do not want to make. */
type SheetSort = 'value_asc' | 'value_desc' | 'date_desc';

const MARKETPLACE_SORTS: { value: SheetSort; label: string }[] = [
  { value: 'date_desc', label: 'Recently listed' },
  { value: 'value_asc', label: 'Price (Low → High)' },
  { value: 'value_desc', label: 'Price (High → Low)' },
];

const SHEET_TO_SORT: Record<SheetSort, P2PSort> = {
  value_asc: 'price_asc',
  value_desc: 'price_desc',
  date_desc: 'newest',
};
const SORT_TO_SHEET: Record<P2PSort, SheetSort> = {
  price_asc: 'value_asc',
  price_desc: 'value_desc',
  newest: 'date_desc',
};

/** Short form for the result-count line. Phrased as the ordering the user sees
 *  ("cheapest first"), not as the API's key name. */
const SORT_SUMMARY: Record<P2PSort, string> = {
  newest: 'newest first',
  price_asc: 'cheapest first',
  price_desc: 'priciest first',
};

function ListingCard({
  listing,
  onPress,
  currency,
  fxRates,
  numberLocale,
}: {
  listing: P2PListing;
  onPress: () => void;
  currency: CurrencyCode;
  fxRates: Settings['fxRates'];
  numberLocale?: NumberLocale;
}) {
  const { colors } = useAppTheme();
  // The seller sets the price in THEIR currency, so a listing can arrive in any
  // of the 7 we support. Formatting `listing.price` with the viewer's currency
  // — which is what this did — printed "€8000" for a ¥8000 card: right number,
  // wrong money, and unusably wrong next to the listing beside it. Convert,
  // then format, so every tile in the grid is comparable.
  const priceLabel = formatPrice(
    convertCurrency(listing.price, (listing.currency as CurrencyCode) || 'EUR', currency, fxRates),
    currency,
    numberLocale,
  );
  return (
    <AnimatedPressable
      onPress={onPress}
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`${listing.title}, ${priceLabel}`}
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
          {priceLabel}
        </Text>
        {/* Social proof, on the TILE. The same number lives on the detail
            screen, but a signal you only see after tapping cannot influence
            whether you tap.

            "3 watching" is the sentence a buyer reads as urgency, and on your
            OWN listing it is the demand signal on your item. */}
        {listing.watchers > 0 ? (
          <View style={styles.watchRow}>
            <Ionicons name="eye-outline" size={11} color={colors.accent} />
            <Text style={[styles.watchText, { color: colors.accent }]}>
              {listing.watchers} watching
            </Text>
          </View>
        ) : null}

        {listing.seller_name && !listing.is_mine ? (
          <View style={styles.cardSeller}>
            <Ionicons name="person-circle-outline" size={13} color={colors.muted} />
            <Text style={[styles.cardSellerName, { color: colors.muted }]} numberOfLines={1}>
              {listing.seller_name}
            </Text>
          </View>
        ) : null}

        <View style={styles.cardMetaRow}>
          {/* Condition + freshness. Research on product cards is consistent
              that condition is decision-critical for second-hand goods, and
              recency is what separates a live marketplace from an abandoned
              one — a grid with no dates reads as a graveyard. */}
          <Text style={[styles.cardMeta, { color: colors.muted }]} numberOfLines={1}>
            {[listing.condition_label, listing.created_at ? timeAgoShort(listing.created_at) : null]
              .filter(Boolean)
              .join(' · ')}
          </Text>
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
  // Debounced so typing costs one request per pause, not per keystroke. `query`
  // stays the value bound to the TextInput so the field itself never lags.
  // Declared up here because both the fetcher and the applied-filter chips read
  // it — the chips show the term that is actually being searched, not the
  // half-typed one.
  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  // A LIST, not one slug. The filter sheet has always been multi-select, so a
  // single value here meant ticking three categories kept one and dropped two
  // without saying so — and the sheet reopened agreeing with itself.
  const [activeCategories, setActiveCategories] = useState<string[]>([]);
  // Seller view. Without this a seller lists something and then cannot find
  // it — the API had a `mine` filter with no way to reach it.
  const [mineOnly, setMineOnly] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sort, setSort] = useState<P2PSort>('newest');
  // Price bounds. Server-side, like `sort`: filtering the loaded page only
  // would look right until the result set outgrows one page.
  const [priceMin, setPriceMin] = useState<number | null>(null);
  const [priceMax, setPriceMax] = useState<number | null>(null);
  // null = not yet known. Rendering the banner before the flag loads would
  // flash it at users who dismissed it months ago.
  const [showIntro, setShowIntro] = useState<boolean | null>(null);

  // Categories that actually have live listings. Until this resolves the sheet
  // gets an empty list and hides its Category section, which is better than
  // offering 54 choices where most guarantee an empty grid.
  const [facets, setFacets] = useState<P2PCategoryFacet[]>([]);
  // Offers waiting on the user. Drives the badge; 0 renders nothing.
  const [offersToAction, setOffersToAction] = useState(0);


  useEffect(() => {
    AsyncStorage.getItem(INTRO_DISMISSED_KEY)
      .then((v) => setShowIntro(v !== '1'))
      .catch(() => setShowIntro(true));
  }, []);

  // Both are decoration on top of the grid: a failure must never block or
  // error the screen, so each swallows into its neutral value and logs.
  // logger.error, not warn — info/warn are stripped from release builds, which
  // is exactly where a silently missing badge would go unnoticed.
  useEffect(() => {
    let cancelled = false;
    collectorsApi
      .listP2PCategoryFacets()
      .then((res) => {
        if (!cancelled) setFacets(res?.facets ?? []);
      })
      .catch((e) => logger.error('[listings] category facets failed:', e));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadOfferCount = useCallback(() => {
    let cancelled = false;
    collectorsApi
      .p2pListOffers('all')
      .then((res) => {
        if (!cancelled) setOffersToAction(countOffersNeedingAction(res?.offers ?? []));
      })
      .catch((e) => logger.error('[listings] offer count failed:', e));
    return () => {
      cancelled = true;
    };
  }, []);

  // useFocusEffect, not useEffect: the badge is the reason to walk into /offers,
  // so it has to be right when you walk BACK out having answered them all —
  // otherwise it keeps advertising work the user already did.
  useFocusEffect(loadOfferCount);

  const dismissIntro = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setShowIntro(false);
    AsyncStorage.setItem(INTRO_DISMISSED_KEY, '1').catch(() => {});
  }, [settings.hapticsEnabled]);

  // Shown on the filter button. An active filter the user cannot see is the
  // classic "why are there no results" trap, so every filter that can narrow
  // the list has to be counted here — a price bound that silently empties the
  // grid with no badge to explain it is the same trap wearing a hat.
  // Each picked category counts, so the badge matches what the sheet shows
  // ticked rather than collapsing "3 categories" to 1.
  const activeFilterCount =
    activeCategories.length +
    (mineOnly ? 1 : 0) +
    (priceMin !== null ? 1 : 0) +
    (priceMax !== null ? 1 : 0);

  // One flag for "the user has narrowed the list", used by the empty state to
  // tell "nothing matches your filters" apart from "the marketplace is empty".
  // Getting this wrong tells a member to be the first to list when there are
  // plenty of listings and their own price bound hid them.
  const hasNarrowingFilters =
    activeFilterCount > 0 || query.trim().length > 0;

  // Sort is deliberately not a "filter" (it hides nothing, so it is not in
  // activeFilterCount, it gets no chip, and Clear leaves it alone) — but that
  // left it completely invisible unless you reopened the sheet. Naming it next
  // to the count is the cheap fix: the ordering of a grid is not self-evident
  // from looking at the grid.
  const sortLabel = SORT_SUMMARY[sort];

  // The prose versions of the price range and category list used to live here,
  // appended to the result count. They were replaced by the applied-filter
  // chips: the chips say the same thing in a form the user can act on, and two
  // adjacent rows describing the same filters is just noise.

  // Only categories with live listings reach the sheet, labelled with their
  // count. A slug the user has already picked is kept even if the facets no
  // longer list it — dropping it would make an active filter disappear from the
  // control while still being applied to the results.
  const filterCategories = useMemo(() => {
    const fromFacets = facets.map((f) => f.category);
    const extras = activeCategories.filter((c) => !fromFacets.includes(c));
    return [...fromFacets, ...extras];
  }, [facets, activeCategories]);

  const categoryChipLabels = useMemo(() => {
    const counts = new Map(facets.map((f) => [f.category, f.count]));
    return Object.fromEntries(
      filterCategories.map((slug) => {
        const name = CATEGORY_SLUG_TO_NAME[slug] ?? slug;
        const n = counts.get(slug);
        return [slug, n != null ? `${name} (${n})` : name];
      }),
    );
  }, [filterCategories, facets]);

  // ONE definition of the sell handoff, used by every entry point on this
  // screen. There were two near-identical copies with different wording, which
  // is how the explanation and the thing it explains drift apart.
  const goSell = useCallback(async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Two routes in, and the second one used not to exist. Sending everyone to
    // their collection assumed everyone HAS one — a marketplace-only seller had
    // to build a collection they did not want before they could sell a single
    // thing (docs/P2P_MARKETPLACE_SPEC.md §5c). Asked every time rather than
    // remembered, because which route is right depends on the item, not on the
    // person: the same seller lists from their collection one day and something
    // they just found in a drawer the next.
    //
    // Collection first: it produces the better listing. It inherits
    // `canonical_key`, so the supply hook writes a buyable row and everyone
    // watching that item is alerted — which is the whole point of the
    // marketplace. The free-text route cannot do that and says so on the screen.
    Alert.alert(
      'Sell an item',
      'From your collection we can suggest a price and alert members already watching it. Otherwise just describe what you have.',
      [
        {
          text: 'From my collection',
          // Goes to a PICKER, not the collection tab. Pushing '/(tabs)/items'
          // dropped the seller into a plain browse screen with no sell mode and
          // no instruction — and the sell action on an item is far below the
          // fold, so the flow read as a dead end (reported 2026-08-08).
          onPress: () => router.push('/sell/pick' as Href),
        },
        {
          text: "It's not in my collection",
          onPress: () => router.push('/sell/new' as Href),
        },
        { text: 'Not now', style: 'cancel' },
      ],
    );
  }, [router, settings.hapticsEnabled]);

  // ── Applied-filters overview ──────────────────────────────────────────────
  // Baymard's product-list research is blunt that a COUNT is not an overview:
  // "when sites just show the number of filters ... there's no applied filters
  // overview", and the user has to reopen the filtering UI to find out what is
  // actually narrowing their results. 28% of benchmarked sites ship no overview
  // at all. It also requires each filter to be individually removable, with
  // "Clear all" kept as a separate control — removing one bad filter should not
  // cost you the four good ones.
  // https://baymard.com/blog/how-to-design-applied-filters
  //
  // This row renders ONLY when something is applied, so the vertical space the
  // redesign fought to reclaim is untouched on a clean screen.
  const appliedFilters = useMemo(() => {
    const out: { key: string; label: string; remove: () => void }[] = [];
    for (const slug of activeCategories) {
      out.push({
        key: `cat:${slug}`,
        label: CATEGORY_SLUG_TO_NAME[slug] ?? slug,
        remove: () => setActiveCategories((prev) => prev.filter((c) => c !== slug)),
      });
    }
    if (mineOnly) {
      out.push({ key: 'mine', label: MINE_FILTER, remove: () => setMineOnly(false) });
    }
    // One chip for the range: "€10–€100" is a single idea, and splitting it into
    // two chips invites half-removals that read as a broken control.
    if (priceMin !== null || priceMax !== null) {
      const fmt = (v: number) => formatPrice(v, settings.currency, settings.numberLocale);
      const label =
        priceMin !== null && priceMax !== null
          ? `${fmt(priceMin)}–${fmt(priceMax)}`
          : priceMin !== null
            ? `over ${fmt(priceMin)}`
            : `under ${fmt(priceMax as number)}`;
      out.push({
        key: 'price',
        label,
        remove: () => {
          setPriceMin(null);
          setPriceMax(null);
        },
      });
    }
    // The search term narrows the list exactly like a filter does, so it belongs
    // in the same overview — otherwise an empty grid has an invisible cause.
    if (debouncedQuery) {
      out.push({
        key: 'q',
        label: `“${debouncedQuery}”`,
        remove: () => setQuery(''),
      });
    }
    return out;
  }, [
    activeCategories, mineOnly, priceMin, priceMax, debouncedQuery,
    settings.currency, settings.numberLocale,
  ]);

  const removeFilter = useCallback(
    (remove: () => void) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      remove();
    },
    [settings.hapticsEnabled],
  );

  const clearFilters = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setActiveCategories([]);
    setMineOnly(false);
    setPriceMin(null);
    setPriceMax(null);
    // Sort is deliberately NOT reset: it is an ordering, not a filter, so it
    // never hides a result and is not part of activeFilterCount either.
  }, [settings.hapticsEnabled]);

  const [refreshing, setRefreshing] = useState(false);

  const fetchListings = useCallback(
    async (limit: number, offset: number) => {
      const res = await collectorsApi.listP2PListings({
        // Sent as repeated params and OR'd server-side, so every category the
        // user ticked is honoured instead of just the first.
        category: activeCategories.length > 0 ? activeCategories : undefined,
        q: debouncedQuery || undefined,
        mine: mineOnly || undefined,
        sort,
        price_min: priceMin ?? undefined,
        price_max: priceMax ?? undefined,
        // The bounds are whatever the user typed, so they are in the currency
        // the user sees. The server converts; sending them bare would compare
        // e.g. "under 100" (JPY) against EUR prices.
        price_currency: settings.currency,
        limit,
        offset,
      });
      return res?.listings ?? [];
    },
    [activeCategories, debouncedQuery, mineOnly, sort, priceMin, priceMax, settings.currency],
  );

  // usePaginatedList rather than useAsync: it caps every page fetch (so a
  // request that never settles cannot pin the skeleton forever) and refetches
  // on reconnect, which useAsync does neither of. The previous version asked
  // for 50 rows once with no way to reach row 51 and nothing on screen
  // admitting the list was truncated.
  const {
    items: listings,
    isLoading: loading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh,
  } = usePaginatedList<P2PListing>(fetchListings, { pageSize: PAGE_SIZE });

  // The hook fetches once on mount and does NOT re-run when the fetcher
  // changes, so a filter change has to ask for the reset explicitly — otherwise
  // the grid keeps showing the previous filter's results. Skipping the first
  // run avoids a duplicate request racing the hook's own initial fetch.
  const didMountRef = useRef(false);
  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    void refresh();
    // `refresh` identity tracks the fetcher, which tracks every filter — so
    // depending on it alone is what makes this fire on exactly the right edges.
  }, [refresh]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } catch (e) {
      logger.error('[listings] refresh failed:', e);
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

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
        fxRates={settings.fxRates}
        numberLocale={settings.numberLocale}
        onPress={() => openListing(item.id)}
      />
    ),
    // fxRates belongs here: SettingsProvider swaps it in when live rates
    // arrive, and without the dep every tile would keep formatting against the
    // rates that happened to be loaded when the screen mounted.
    [openListing, settings.currency, settings.fxRates, settings.numberLocale],
  );

  return (
    // Plain View, NOT SafeAreaView: ScreenHeader already applies
    // `insets.top` (ScreenHeader.tsx:43). Wrapping in SafeAreaView too would
    // double-pad the top — the playbook's SafeAreaView rule is for screens
    // WITHOUT this header.
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Marketplace" />

      {/*
        REDESIGNED 2026-08-07 after a UX review. The previous version stacked
        SIX rows of chrome before a single product: an offers card, a
        Browse/My-listings segment, a search bar, 12 flat category chips, and a
        result count. On mobile, vertical space is the scarcest resource and
        research is consistent that users engage more with FEW well-chosen
        controls than a full panel — so the filters moved behind progressive
        disclosure and the grid now starts near the top, the way Vinted and
        Depop open straight onto photos.

        Two specific fixes:
        - "My listings" was a segmented control on the BROWSE screen. That is
          an implementation detail leaking into the UI: a first-time user with
          nothing listed saw a toggle for something they do not have. It is now
          a filter inside the sheet, where "show only mine" actually belongs.
        - "Your offers" was a full-width card in prime real estate. An inbox is
          not a product; it is now an icon with a count.
      */}
      <Animated.View style={[styles.controls, animatedStyle]}>
        {/* First-visit explainer. Research on marketplace onboarding is blunt
            that the first impression is a silent drop-off point: a user who
            cannot tell WHAT a screen is leaves rather than asks. This names
            the three things that are not obvious from a grid of photos —
            these are other members' items, we don't handle payment, and you
            can sell here too — then gets out of the way permanently. */}
        {showIntro ? (
          <View style={[styles.intro, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '33' }]}>
            <View style={styles.introHead}>
              <Ionicons name="people-outline" size={16} color={colors.accent} />
              <Text style={[styles.introTitle, { color: colors.text }]}>Buy and sell with other members</Text>
              <AnimatedPressable
                onPress={dismissIntro}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                accessibilityRole="button"
                accessibilityLabel="Dismiss introduction"
              >
                <Ionicons name="close" size={16} color={colors.muted} />
              </AnimatedPressable>
            </View>
            <Text style={[styles.introBody, { color: colors.muted }]}>
              Everything here is listed by collectors like you. Message a seller to
              agree a price — Sparrow doesn&apos;t handle payment or delivery. List
              your own items and members watching them get alerted.
            </Text>
          </View>
        ) : null}

        <View style={styles.searchRow}>
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

          {/* Offers as an icon, not a card — but an icon with a COUNT. An
              unbadged glyph is the weakest possible signal for the one thing on
              this screen that is time-sensitive: an offer nobody answers is a
              lost sale. The badge counts only offers waiting on THIS user
              (offerNeedsMyAction), so it never nags about something that is
              someone else's turn. */}
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push('/offers' as Href);
            }}
            style={[
              styles.iconBtn,
              { backgroundColor: colors.card,
                borderColor: offersToAction > 0 ? colors.accent : colors.border },
            ]}
            accessibilityRole="button"
            accessibilityLabel={
              offersToAction > 0
                ? `Your offers, ${offersToAction} waiting for you`
                : 'Your offers'
            }
          >
            <Ionicons
              name="swap-horizontal-outline"
              size={18}
              color={offersToAction > 0 ? colors.accent : colors.text}
            />
            {offersToAction > 0 ? (
              <View style={[styles.badge, { backgroundColor: colors.accent, borderColor: colors.background }]}>
                <Text style={[styles.badgeText, { color: colors.accentText }]}>
                  {offersToAction > 9 ? '9+' : offersToAction}
                </Text>
              </View>
            ) : null}
          </AnimatedPressable>
        </View>

        {/* ONE control row. The filter button carries a count so the user can
            always see how much is being hidden from them — an invisible active
            filter is the classic "why are there no results" trap. */}
        <View style={styles.filterRow}>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setFilterOpen(true);
            }}
            style={[
              styles.filterBtn,
              { borderColor: activeFilterCount > 0 ? colors.accent : colors.border,
                backgroundColor: activeFilterCount > 0 ? colors.accent + '14' : colors.card },
            ]}
            accessibilityRole="button"
            accessibilityLabel={activeFilterCount > 0 ? `Filters, ${activeFilterCount} active` : 'Filter and sort'}
          >
            <Ionicons name="options-outline" size={15} color={activeFilterCount > 0 ? colors.accent : colors.text} />
            <Text style={[styles.filterBtnText, { color: activeFilterCount > 0 ? colors.accent : colors.text }]}>
              {activeFilterCount > 0 ? `Filters · ${activeFilterCount}` : 'Filter & sort'}
            </Text>
          </AnimatedPressable>

          {activeFilterCount > 0 ? (
            <AnimatedPressable
              onPress={clearFilters}
              style={styles.clearBtn}
              accessibilityRole="button"
              accessibilityLabel="Clear all filters"
            >
              <Text style={[styles.clearBtnText, { color: colors.accent }]}>Clear</Text>
            </AnimatedPressable>
          ) : null}

          <View style={styles.grow} />

          {/* Sell is the other half of a marketplace and had no entry point on
              this screen at all — a browse-only surface tells a member this is
              somewhere to look, not somewhere to participate. */}
          <AnimatedPressable
            onPress={goSell}
            style={[styles.sellBtn, { backgroundColor: colors.accent }]}
            accessibilityRole="button"
            accessibilityLabel="Sell an item from your collection"
          >
            <Ionicons name="add" size={15} color={colors.accentText} />
            <Text style={[styles.sellBtnText, { color: colors.accentText }]}>Sell</Text>
          </AnimatedPressable>
        </View>
      </Animated.View>

      {/* Applied-filters overview — one removable chip per active filter.
          Horizontally scrolling rather than wrapping to multiple rows: the
          research allows either, and wrapping would push the grid down by an
          unpredictable amount, which is the one thing this screen's redesign was
          fighting. The numeric count stays on the Filter button, which doubles
          as the "there is more, scroll" cue the research asks for on mobile. */}
      {appliedFilters.length > 0 ? (
        // A WRAPPING row, not a horizontal FlatList. The first attempt used a
        // horizontal list and it rendered two correctly-styled but EMPTY pills:
        // a horizontal FlatList in a flex column has no intrinsic height, so it
        // collapsed and clipped its own children. Wrapping is the other layout
        // the research endorses ("spread the filters over as many rows as are
        // needed ... users see all applied filters without scrolling
        // horizontally") and it removes both the height fragility and the
        // off-screen-truncation problem. There are at most a handful of chips
        // here — categories plus price, mine and the search term.
        <View style={styles.chipsWrap}>
          {appliedFilters.map((f) => (
            <AnimatedPressable
              key={f.key}
              onPress={() => removeFilter(f.remove)}
              style={[
                styles.appliedChip,
                { backgroundColor: colors.accent + '14', borderColor: colors.accent + '55' },
              ]}
              // The whole chip removes the filter, not just the ×: a 13pt glyph
              // is far under the 44pt minimum, and there is nothing else a tap
              // on an applied filter could plausibly mean.
              accessibilityRole="button"
              accessibilityLabel={`Remove filter ${f.label}`}
            >
              <Text style={[styles.appliedChipText, { color: colors.accent }]} numberOfLines={1}>
                {f.label}
              </Text>
              <Ionicons name="close" size={13} color={colors.accent} />
            </AnimatedPressable>
          ))}
        </View>
      ) : null}

      {/* Result count: cheap orientation, and it makes a filter that matched
          nothing obvious before the user scrolls. */}
      {!loading && !error && listings.length > 0 ? (
        <Text style={[styles.resultCount, { color: colors.muted }]}>
          {/* Count + ordering only. WHICH filters are applied is now the chips
              row directly above, so restating it here said the same thing twice
              in two adjacent rows. */}
          {mineOnly
            ? `Your ${listings.length} listing${listings.length === 1 ? '' : 's'}`
            : `${listings.length} listing${listings.length === 1 ? '' : 's'}`}
          {` · ${sortLabel}`}
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
              onPress={() => refresh()}
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
          // 0.5 rather than the default 2: at 2 the next page is requested a
          // full two screens early, which on a short grid fires immediately on
          // mount and fetches page 2 before the user has scrolled at all.
          onEndReached={() => loadMore()}
          onEndReachedThreshold={0.5}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />
          }
          ListEmptyComponent={
            // Demand-aware, not apologetic. "No listings yet" tells a seller
            // nothing happens here; naming the waiting demand is the strongest
            // seller-acquisition line we have, and it is the one thing a
            // generic marketplace cannot say (docs/P2P_MARKETPLACE_SPEC.md).
            // Three DIFFERENT situations, and conflating them misinforms:
            //   - the seller has listed nothing            → tell them how to
            //   - filters/search excluded everything       → offer to undo them
            //   - the marketplace itself is empty          → recruit a seller
            // The middle case previously tested only `query || activeCategory`,
            // so a price bound that hid every listing fell through to "Be the
            // first to list" — telling a member the marketplace is empty when
            // it is not, and pointing them at selling instead of at the filter
            // that actually caused it.
            <View style={styles.empty}>
              <Ionicons
                name={hasNarrowingFilters && !mineOnly ? 'filter-outline' : 'pricetags-outline'}
                size={44}
                color={colors.muted}
              />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                {mineOnly
                  ? 'You have no listings yet'
                  : hasNarrowingFilters
                    ? 'No listings match your filters'
                    : 'Be the first to list'}
              </Text>
              <Text style={[styles.emptyBody, { color: colors.muted }]}>
                {mineOnly
                  ? 'Open any item in your collection and tap Sell this. It appears here straight away.'
                  : hasNarrowingFilters
                  ? 'There may be listings outside your current filters. Widen the price range, pick another category, or clear the search.'
                  : 'Members set target prices on the things they want. List an item you own and they get alerted the moment it matches — open any item in your collection and tap Sell this.'}
              </Text>
              {/* The CTA has to undo the cause. Offering "sell something" to a
                  user whose own price bound emptied the grid is a dead end. */}
              {hasNarrowingFilters && !mineOnly ? (
                <AnimatedPressable
                  onPress={() => {
                    clearFilters();
                    setQuery('');
                  }}
                  style={[styles.cta, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Clear all filters and search"
                >
                  <Text style={[styles.ctaText, { color: colors.accentText }]}>
                    Clear filters
                  </Text>
                </AnimatedPressable>
              ) : (
                <AnimatedPressable
                  onPress={goSell}
                  style={[styles.cta, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Choose an item from your collection to sell"
                >
                  <Text style={[styles.ctaText, { color: colors.accentText }]}>
                    Choose an item to sell
                  </Text>
                </AnimatedPressable>
              )}
            </View>
          }
          ListFooterComponent={
            listings.length > 0 ? (
              <View style={styles.footerWrap}>
                {/* Paging state, ABOVE the legal note. A grid that silently
                    stops looks identical to a grid that has run out; saying
                    which is the difference between "keep scrolling" and "this
                    is everything". */}
                {isLoadingMore ? (
                  <View style={styles.footerLoading}>
                    <ActivityIndicator size="small" color={colors.accent} />
                    <Text style={[styles.footerNote, { color: colors.muted }]}>
                      Loading more…
                    </Text>
                  </View>
                ) : !hasMore ? (
                  <Text style={[styles.footerNote, { color: colors.muted }]}>
                    That&apos;s all {listings.length} listing{listings.length === 1 ? '' : 's'}.
                  </Text>
                ) : null}
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

      <FilterSheet
        visible={filterOpen}
        onClose={() => setFilterOpen(false)}
        currentConfig={{
          categories: activeCategories,
          priceMin,
          priceMax,
          // "Only mine" rides in `conditions` rather than a new field: the
          // sheet is shared with other screens and widening its contract for
          // one caller would push this concept onto all of them. The section
          // heading is retitled instead — see MINE_SECTION_TITLE.
          conditions: mineOnly ? [MINE_FILTER] : [],
          sortBy: SORT_TO_SHEET[sort],
        }}
        onApply={(cfg: FilterConfig) => {
          // Every ticked category, not just the first — the API ORs them.
          setActiveCategories(cfg.categories);
          setMineOnly(cfg.conditions.includes(MINE_FILTER));
          // Both of these were previously collected by the sheet and thrown
          // away, while the button read "Filter & sort" — a control that
          // promises something it does not do. The sheet's sort list is now
          // narrowed to the three keys the API actually supports, so the
          // mapping is exact rather than a fold onto 'newest'.
          setSort(SHEET_TO_SORT[cfg.sortBy as SheetSort] ?? 'newest');
          setPriceMin(cfg.priceMin);
          setPriceMax(cfg.priceMax);
          setFilterOpen(false);
        }}
        // Facet-driven: only categories that have live listings, each labelled
        // with its count. Offering all 54 meant most choices guaranteed an
        // empty grid, discoverable only by paying a round trip.
        availableCategories={filterCategories}
        categoryLabels={categoryChipLabels}
        availableConditions={[MINE_FILTER]}
        conditionsTitle={MINE_SECTION_TITLE}
        sortOptions={MARKETPLACE_SORTS}
        // The bounds are read in the user's display currency and converted
        // server-side, so the fields have to say which currency that is.
        priceCurrencySymbol={getCurrencySymbol(settings.currency)}
        colors={colors}
      />

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
  intro: {
    borderWidth: 1, borderRadius: radius.md,
    padding: 12, marginBottom: 10, gap: 6,
  },
  introHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  introTitle: { flex: 1, fontSize: textToken.sm, fontWeight: fontWeight.bold },
  introBody: { fontSize: textToken.xs, lineHeight: 17 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  iconBtn: {
    width: 40, height: 40, borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center', justifyContent: 'center',
  },
  // Sits on the button's top-right corner. `overflow` is not clipped on the
  // parent, so the negative offsets are safe; the border matches the screen
  // background so the pill reads as lifted off the button beneath it.
  badge: {
    position: 'absolute', top: -5, right: -5,
    minWidth: 17, height: 17, borderRadius: 9, borderWidth: 1.5,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3,
  },
  badgeText: { fontSize: 10, fontWeight: fontWeight.bold, lineHeight: 13 },
  chipsWrap: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8,
    paddingHorizontal: 16, marginTop: 10,
  },
  appliedChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderRadius: radius.pill,
    // 7pt vertical keeps the row compact; the chip is ~32pt tall and the whole
    // chip is the hit target, which is what carries it past a comfortable tap.
    paddingHorizontal: 12, paddingVertical: 7,
    maxWidth: 220,
  },
  appliedChipText: { fontSize: textToken.sm, fontWeight: fontWeight.semibold, flexShrink: 1 },
  footerLoading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  filterRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  filterBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderRadius: radius.pill,
    paddingHorizontal: 12, paddingVertical: 7,
  },
  filterBtnText: { fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  clearBtn: { paddingHorizontal: 4, paddingVertical: 7 },
  clearBtnText: { fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  grow: { flex: 1 },
  sellBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderRadius: radius.pill, paddingHorizontal: 14, paddingVertical: 7,
  },
  sellBtnText: { fontSize: textToken.sm, fontWeight: fontWeight.bold },
  searchBar: {
    // flex: 1 is REQUIRED now that this shares a row with the offers button.
    // Without it the bar takes its intrinsic width (the TextInput inside is
    // flex: 1 and grows greedily) and pushes the 40pt icon off the right edge —
    // the offers entry point rendered as a clipped sliver. Only visible in a
    // real render; the layout is perfectly valid to tsc and to the tests.
    flex: 1,
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
  watchRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  watchText: { fontSize: 10, fontWeight: fontWeight.bold },
  cardSeller: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 2 },
  cardSellerName: { flex: 1, fontSize: 11 },
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
