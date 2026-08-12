/**
 * Global Unified Search Screen
 * Searches across items, catalog, collectors, events, and categories.
 */
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
// react-native's Image is already imported above for the result rows; the
// tiles want expo-image for caching + transitions, so alias it.
import { Image as ExpoImage } from 'expo-image';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { dataProvider } from '@/data';
import { getCategoryById, CATEGORIES } from '@/data/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { SkeletonList } from '@/components/Skeleton';
import { SlowLoadNotice } from '@/components/SlowLoadNotice';
import { useSlowLoad } from '@/hooks/useSlowLoad';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { radius, text, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';
import { useTranslation } from 'react-i18next';
import { fmtCurrency } from '@/lib/format';
import { useSettings } from '@/lib/settings';
import { safeGoBack } from '@/lib/goBack';

// Recent searches removed 2026-08-07. The AsyncStorage key
// '@sparrowcollect/recent_searches' is deliberately cleared once on mount
// below rather than left behind: an orphaned key keeps a user's search
// history on the device indefinitely after the feature that justified
// collecting it is gone, which is the kind of quiet data retention a privacy
// policy should not have to cover.
const LEGACY_RECENT_SEARCHES_KEY = '@sparrowcollect/recent_searches';

type SearchResults = {
  items: { id: string; name: string; category: string; imageUrl?: string | null; price?: number }[];
  catalog: { id: string; category: string; itemKey: string; title: string; brand?: string | null; hasReferenceImage?: boolean; priceEur?: number | null }[];
  users: { id: string; displayName: string; handle?: string; avatarUrl?: string | null }[];
  events: { id: string; title: string; startDate?: string; location?: string; category?: string }[];
  categories: { id: string; name: string }[];
};

const ItemSearchResult = React.memo(function ItemSearchResult({ item, colors, onPress }: { item: SearchResults['items'][number]; colors: ReturnType<typeof useAppTheme>['colors']; onPress: () => void }) {
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${item.name}`}
    >
      {item.imageUrl ? (
        <Image source={{ uri: item.imageUrl }} style={resultStyles.resultThumb} />
      ) : (
        <View style={[resultStyles.resultThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
          <Ionicons name="cube-outline" size={18} color={colors.accent} />
        </View>
      )}
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{item.name}</Text>
        <Text style={[resultStyles.resultSubtitle, { color: colors.muted }]}>{item.category}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.muted} />
    </AnimatedPressable>
  );
});

const CatalogSearchResult = React.memo(function CatalogSearchResult({ item, colors, onPress }: { item: SearchResults['catalog'][number]; colors: ReturnType<typeof useAppTheme>['colors']; onPress: () => void }) {
  const { t } = useTranslation();
  // price_eur is EUR-denominated; fmtCurrency converts it into the user's
  // selected currency with their fxRates and number locale. formatPrice(x,'EUR')
  // would have shown EUR to a user set to USD or JPY, disagreeing with every
  // other price in the app.
  const { settings } = useSettings();
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${item.title} in catalog`}
    >
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{item.title}</Text>
        <Text style={[resultStyles.resultSubtitle, { color: colors.muted }]}>
          {item.brand ? `${item.brand} · ${item.category}` : item.category}
        </Text>
      </View>
      {/* Absent price is stated, never blank. A silent gap reads as a loading
          bug; "No price yet" says we know the object and not its value — which
          is the honest position for the categories with no sold-comp source. */}
      {typeof item.priceEur === 'number' ? (
        <Text style={[resultStyles.resultPrice, { color: colors.text }]} numberOfLines={1}>
          {fmtCurrency(item.priceEur, settings)}
        </Text>
      ) : (
        <Text style={[resultStyles.resultNoPrice, { color: colors.muted }]} numberOfLines={1}>
          {t('search.no_price_yet')}
        </Text>
      )}
      <Ionicons name="chevron-forward" size={16} color={colors.muted} />
    </AnimatedPressable>
  );
});

const UserSearchResult = React.memo(function UserSearchResult({ user, colors, onPress }: { user: SearchResults['users'][number]; colors: ReturnType<typeof useAppTheme>['colors']; onPress: () => void }) {
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${user.displayName}'s profile`}
    >
      {user.avatarUrl ? (
        <Image source={{ uri: user.avatarUrl }} style={resultStyles.resultAvatar} />
      ) : (
        <View style={[resultStyles.resultThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
          <Ionicons name="person-outline" size={18} color={colors.accent} />
        </View>
      )}
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{user.displayName}</Text>
        {user.handle && <Text style={[resultStyles.resultSubtitle, { color: colors.muted }]}>@{user.handle}</Text>}
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.muted} />
    </AnimatedPressable>
  );
});

const EventSearchResult = React.memo(function EventSearchResult({ event, colors, onPress }: { event: SearchResults['events'][number]; colors: ReturnType<typeof useAppTheme>['colors']; onPress: () => void }) {
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${event.title}`}
    >
      <Ionicons name="calendar-outline" size={20} color={colors.accent} />
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{event.title}</Text>
        {event.location && <Text style={[resultStyles.resultSubtitle, { color: colors.muted }]}>{event.location}</Text>}
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.muted} />
    </AnimatedPressable>
  );
});

const CategorySearchResult = React.memo(function CategorySearchResult({ cat, colors, onPress }: { cat: SearchResults['categories'][number]; colors: ReturnType<typeof useAppTheme>['colors']; onPress: () => void }) {
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Browse ${cat.name}`}
    >
      <Ionicons name="grid-outline" size={20} color={colors.accent} />
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{cat.name}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.muted} />
    </AnimatedPressable>
  );
});

// Shared styles for search result components (referenced before SearchScreen)
const resultStyles = StyleSheet.create({
  resultRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, gap: 12 },
  resultThumb: { width: 36, height: 36, borderRadius: radius.xs },
  resultAvatar: { width: 36, height: 36, borderRadius: radius.lg },
  resultThumbPlaceholder: { width: 36, height: 36, borderRadius: radius.xs, alignItems: 'center', justifyContent: 'center' },
  resultInfo: { flex: 1 },
  resultTitle: { fontSize: text.lg, fontWeight: fontWeight.medium },
  resultSubtitle: { fontSize: text.md, marginTop: 2 },
  // Right-aligned with a floor width so a column of prices lines up instead of
  // jittering with each value's length.
  resultPrice: { fontSize: text.md, fontWeight: '600', minWidth: 64, textAlign: 'right' },
  resultNoPrice: { fontSize: text.sm, minWidth: 64, textAlign: 'right' },
});

/**
 * @param asTab Rendered as the Search TAB rather than as a pushed route.
 *
 *   This governs the two affordances that only make sense on a PUSHED screen:
 *
 *   - the in-body `QuickNavBar`. The tab already sits inside the tabs
 *     navigator, so rendering both stacks two navigation bars and the lower one
 *     covers the last rows of the results list.
 *   - the back chevron. A tab has nothing to go back TO; `safeGoBack` would
 *     find an empty stack and fall back to `/(tabs)`, so the control would look
 *     like "back" and behave like "jump to Portfolio".
 *
 *   FALSE for `/search`, which is pushed from the market search bar or opened
 *   by deep link and genuinely needs both.
 */
// Browse-by-category moved here from the Market tab 2026-08-11. Browsing a
// taxonomy IS a search act, and this screen is where search lives.
const BROWSE_CATEGORIES = CATEGORIES.map((cat) => ({
  id: cat.id,
  name: cat.name,
  imageUrl: cat.bannerImageUrl,
}));

function SearchScreen({ asTab = false }: { asTab?: boolean }) {
  const router = useRouter();
  // Unconditional, and NOT gated on `asTab`: this screen always has exactly one
  // absolutely-positioned bar over its bottom edge, and both are the same
  // height (58 + max(insets.bottom, 10)). As a tab it is `ExternalTabBar`,
  // rendered at the root stack; pushed it is the `QuickNavBar` below. Neither
  // reserves layout space, so without this the last result row is drawn
  // underneath the bar — 36pt of it on a flat phone, 60pt on a notched one.
  const bottomInset = useTabBarInset();
  const { colors, isDark } = useAppTheme();
  const { t } = useTranslation();
  // Seeded from `?q=`, which the marketplace search bar now sends when a query
  // is submitted (2026-08-10). A lazy initialiser, NOT an effect: params are
  // present on the first render, and an effect that wrote `query` while also
  // depending on it is the self-cancelling pattern
  // scripts/check-self-cancelling-effects.mjs exists to catch. Same shape the
  // marketplace screen already uses for its own `?q=`.
  const { q: initialQuery } = useLocalSearchParams<{ q?: string }>();
  const [query, setQuery] = useState(() => (typeof initialQuery === 'string' ? initialQuery : ''));
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const { isSlow, isVerySlow } = useSlowLoad(loading);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [error, setError] = useState(false);

  // One-time cleanup of the removed recent-searches feature. Cheap, idempotent,
  // and it means uninstalling the feature also uninstalls the data it kept.
  useEffect(() => {
    AsyncStorage.removeItem(LEGACY_RECENT_SEARCHES_KEY).catch(() => {});
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults(null);
      setError(false);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const res = await dataProvider.unifiedSearch(q.trim());
      setResults(res ?? null);
    } catch (e) {
      // logger.error, not warn: info/warn are stripped from release builds, so
      // a failed search would have left no trace on exactly the builds where
      // "search found nothing" gets reported. The error STATE was already
      // rendered — this only makes the cause recoverable from getRecentLogs().
      logger.error('[search] unified search failed:', e);
      setResults(null);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleQueryChange = useCallback((text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(text), 300);
  }, [doSearch]);

  // Run a seeded `?q=` once, on mount.
  //
  // `doSearch` is otherwise only ever reached through `handleQueryChange`, i.e.
  // by typing. Without this the incoming query would render in the input and
  // never search — the param would be accepted and silently dropped, which is
  // exactly the dead route-param handoff `npm run check:params` exists to catch.
  //
  // Mount-only, and it calls `doSearch` directly rather than `setQuery`: it must
  // not list `query` in its deps while also writing it, which is the
  // self-cancelling-effect pattern (scripts/check-self-cancelling-effects.mjs).
  useEffect(() => {
    if (typeof initialQuery === 'string' && initialQuery.trim()) {
      doSearch(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  /*
   * A category row is the one result kind whose id IS the route, so an id the
   * app has no screen for renders a result that goes nowhere.
   *
   * The server builds its own hand-written CATEGORY_LIST, and three of its 36
   * ids do not exist in `src/data/categories.ts`: it sends `pokemon_tcg`,
   * `sports_cards` and `kpop` where the app's ids are `pokemon`, `sportscards`
   * and `kpop_merch`. Tapping one pushed `/categories/pokemon_tcg`, which
   * `getCategoryById` cannot resolve, so the screen rendered "Category not
   * found" — on the single most-searched word in a collectibles app.
   *
   * Resolved here against the LOCAL taxonomy, the same source
   * `app/categories/[categoryId].tsx` routes with, so a category row can only
   * render when its destination exists. The server list is corrected too, and
   * `npm run check:search-categories` fails the build if the two drift again —
   * this filter is what keeps a future drift from reaching a user's thumb
   * rather than only a CI log.
   */
  const routableCategories = useMemo(
    () => (results?.categories ?? []).filter((c) => getCategoryById(c.id) !== undefined),
    [results],
  );

  // Counts what is RENDERED, not what arrived: an unroutable category row is
  // filtered out above, and counting it here would leave a query whose only
  // hits were unroutable showing an empty screen with no "no results" state.
  const totalResults = results
    ? results.items.length + results.catalog.length + results.users.length + results.events.length + routableCategories.length
    : 0;

  const hasResults = results && totalResults > 0;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {/* Search Header */}
      <View style={styles.header}>
        {!asTab && (
          <AnimatedPressable onPress={() => safeGoBack(router)} style={styles.backBtn} accessibilityRole="button" accessibilityLabel={t('common.go_back')}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
        )}
        <View style={[styles.searchBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder={t('search.placeholder')}
            placeholderTextColor={colors.muted}
            value={query}
            onChangeText={handleQueryChange}
            // Focus only when the user arrived here TO TYPE.
            //
            // Bare `autoFocus` raised the keyboard the instant the Search TAB
            // opened, covering the browse-by-category grid that is the tab's
            // whole idle state — the categories are the reason to open the tab
            // without a query, and they were hidden before they could be read.
            // Same reasoning as the back chevron and QuickNavBar above: a tab
            // is somewhere you land, a pushed screen is somewhere you chose to
            // go.
            //
            // Also suppressed when arriving with `?q=` (item detail's "view all
            // marketplace results" pushes /search?q=): the query is already
            // filled and the results are what you came to read, so opening the
            // keyboard over them helps nobody. Tapping the bar still focuses in
            // every case.
            autoFocus={!asTab && !initialQuery}
            returnKeyType="search"
            accessibilityLabel={t('search.input_a11y')}
          />
          {query.length > 0 && (
            <AnimatedPressable onPress={() => { setQuery(''); setResults(null); }} accessibilityRole="button" accessibilityLabel={t('common.clear_search')}>
              <Ionicons name="close-circle" size={18} color={colors.muted} />
            </AnimatedPressable>
          )}
        </View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={[styles.scrollContent, { paddingBottom: bottomInset }]} keyboardShouldPersistTaps="handled">
        {/* Idle state: no query typed. A search screen with an empty body is a
            dead end — the taxonomy gives somewhere to go. Hidden the moment a
            query exists so it never competes with results. */}
        {!loading && query.trim().length === 0 && (
          <View style={styles.browseSection}>
            <Text style={[styles.browseTitle, { color: colors.text }]}>
              {t('search.browse_by_category')}
            </Text>
            <View style={styles.browseGrid}>
              {BROWSE_CATEGORIES.map((cat, index) => {
                const row = Math.floor(index / 2);
                const col = index % 2;
                const ci = (row + col) % 2 === 0
                  ? (row % 2 === 0 ? 0 : 1)
                  : (row % 2 === 0 ? 2 : 3);
                const darkTileColors = [colors.accent + '70', colors.accent + '90', colors.accent + 'B0', colors.accent + 'D0'];
                const bg = isDark ? darkTileColors[ci] : colors.tileScale[ci];
                return (
                  <AnimatedPressable
                    key={cat.id}
                    style={[styles.categoryTile, { backgroundColor: bg }]}
                    onPress={() => router.push(`/categories/${cat.id}` as Href)}
                    accessibilityRole="button"
                    accessibilityLabel={`Browse ${cat.name}`}
                  >
                    {cat.imageUrl ? (
                      <ExpoImage
                        source={{ uri: cat.imageUrl }}
                        style={styles.categoryTileImage}
                        contentFit="cover"
                        cachePolicy="memory-disk"
                        transition={150}
                      />
                    ) : null}
                    <View style={styles.categoryTileOverlay} />
                    <Text style={styles.categoryTileText} numberOfLines={2} ellipsizeMode="tail">
                      {cat.name}
                    </Text>
                  </AnimatedPressable>
                );
              })}
            </View>
          </View>
        )}

        {loading && (
          <View style={styles.loadingContainer}>
            <SkeletonList count={6} />
            {/* Search fans out across items, catalog, users and events, so it
                is the slowest read in the app and the one most likely to look
                stuck. Silent under 3s. */}
            <SlowLoadNotice isSlow={isSlow} isVerySlow={isVerySlow} />
          </View>
        )}

        {!loading && error && (
          <View style={styles.emptyContainer}>
            <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.emptyText, { color: colors.muted }]}>{t('search.unavailable')}</Text>
            <AnimatedPressable onPress={() => doSearch(query)} style={{ marginTop: 12, paddingHorizontal: 20, paddingVertical: 10, borderRadius: radius.xs, backgroundColor: colors.accent }} accessibilityRole="button" accessibilityLabel={t('search.retry_a11y')}>
              <Text style={{ color: colors.accentText, fontWeight: fontWeight.semibold, fontSize: text.md }}>{t('common.retry_action')}</Text>
            </AnimatedPressable>
          </View>
        )}

        {!loading && !error && query.length > 0 && !hasResults && (
          <View style={styles.emptyContainer}>
            <Ionicons name="search-outline" size={48} color={colors.muted} />
            <Text style={[styles.emptyText, { color: colors.muted }]}>{t('search.no_results')}</Text>
          </View>
        )}

        {/* Items Section */}
        {results && results.items.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">ITEMS</Text>
            {results.items.map((item) => (
              <ItemSearchResult key={item.id} item={item} colors={colors} onPress={() => router.push(`/item/${item.id}` as Href)} />
            ))}
          </View>
        )}

        {/* Catalog Section */}
        {results && results.catalog.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">CATALOG</Text>
            {results.catalog.map((catItem) => (
              <CatalogSearchResult
                key={catItem.id}
                item={catItem}
                colors={colors}
                /*
                 * Opens the ITEM, not its category (fixed 2026-08-11).
                 *
                 * This used to push `/categories/${category}`, so tapping the
                 * "Rolex Cosmograph Daytona" you had just searched for dropped
                 * you on the whole Watches category page — the one screen that
                 * cannot show you the row you tapped. Reported as "the results
                 * are not pressable": the press fired, the screen changed, and
                 * the thing the user asked for was nowhere on it.
                 *
                 * `/catalog-item/[key]` is the destination every other catalog
                 * surface already uses (CategoryOverviewRail, catalog-set,
                 * the museum's own sibling rail) — one destination for "open a
                 * catalog row", not a second one that only search knows about.
                 *
                 * Search returns no image_url (kept backend-only), no rarity and
                 * no set_code, so those params go empty. The museum degrades
                 * cleanly: it renders a placeholder thumbnail, skips the
                 * "from this set" rail, and re-fetches the price itself via
                 * getCatalogItemPrice(category, key) — so an unpriced row here
                 * is never LESS informative than the same row reached from a
                 * category rail.
                 */
                onPress={() => router.push({
                  pathname: '/catalog-item/[key]',
                  params: {
                    key: catItem.itemKey,
                    category: catItem.category,
                    title: catItem.title,
                    brand: catItem.brand ?? '',
                    image_url: '',
                    rarity: '',
                    set_code: '',
                    // Empty, never "0": the museum parses this with parseFloat
                    // and an unpriced watch must arrive as "no price", not as
                    // a EUR 0 valuation (unknown-as-zero).
                    estimated_price: catItem.priceEur != null ? String(catItem.priceEur) : '',
                  },
                } as unknown as Href)}
              />
            ))}
          </View>
        )}

        {/* Users Section */}
        {results && results.users.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">COLLECTORS</Text>
            {results.users.map((user) => (
              <UserSearchResult key={user.id} user={user} colors={colors} onPress={() => router.push(`/users/${user.id}` as Href)} />
            ))}
          </View>
        )}

        {/* Events Section */}
        {results && results.events.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">EVENTS</Text>
            {results.events.map((event) => (
              <EventSearchResult key={event.id} event={event} colors={colors} onPress={() => router.push(`/events/${event.id}` as Href)} />
            ))}
          </View>
        )}

        {/* Categories Section */}
        {routableCategories.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">CATEGORIES</Text>
            {routableCategories.map((cat) => (
              <CategorySearchResult key={cat.id} cat={cat} colors={colors} onPress={() => router.push(`/categories/${cat.id}` as Href)} />
            ))}
          </View>
        )}
        {/* No trailing spacer: `bottomInset` on contentContainerStyle already
            clears the bar. A hand-picked height on top of it is the pattern
            that clipped the last row on five other (tabs) screens — see
            docs/ui-playbook.md and src/hooks/useTabBarInset.ts. */}
      </ScrollView>
      {!asTab && <QuickNavBar />}
    </SafeAreaView>
  );
}

export default function SearchScreenWithBoundary({ asTab }: { asTab?: boolean } = {}) {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchScreen asTab={asTab} />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 8, gap: 8 },
  backBtn: { padding: 8 },
  searchBar: { flex: 1, flexDirection: 'row', alignItems: 'center', borderRadius: radius.md, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  searchInput: { flex: 1, fontSize: text.lg, padding: 0 },
  scroll: { flex: 1 },
  browseSection: { paddingTop: 8 },
  browseTitle: { fontSize: text.lg, fontWeight: fontWeight.bold, marginBottom: 12 },
  browseGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  categoryTile: {
    width: '48.5%',
    height: 96,
    borderRadius: radius.md,
    marginBottom: 12,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  categoryTileImage: { ...StyleSheet.absoluteFillObject },
  categoryTileOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.28)' },
  categoryTileText: {
    color: '#fff',
    fontSize: text.sm,
    fontWeight: fontWeight.bold,
    padding: 10,
  },
  scrollContent: { paddingHorizontal: 16 },
  loadingContainer: { paddingVertical: 32, alignItems: 'center' },
  emptyContainer: { paddingVertical: 48, alignItems: 'center', gap: 12 },
  emptyText: { fontSize: text.lg },
  section: { marginTop: 20 },
  sectionTitle: { fontSize: text.sm, fontWeight: fontWeight.semibold, letterSpacing: 0.5, marginBottom: 8 },
});
