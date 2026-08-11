/**
 * Market hub — search, collectors, open bids, demand heat, movers, regional.
 *
 * WAS `app/(tabs)/marketplace.tsx` until 2026-08-11. The Market TAB now opens
 * straight onto the member marketplace grid (app/listings.tsx) rather than
 * onto this hub, because a tab called Market that opened a search page was a
 * name and a destination that disagreed.
 *
 * Moved rather than deleted, and it keeps an entry point from the grid's
 * control row — every section in here is live and none of it is rebuilt
 * anywhere else. Browse-by-category is the one thing that did move out; it
 * lives on the Search tab now.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useModal } from '@/hooks/useModal';
import { useDebounce } from "@/hooks/useDebounce";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
  ActivityIndicator,
  Linking,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  Modal,
  TouchableOpacity,
  Share,
  FlatList,
} from "react-native";
// react-native's own SafeAreaView is iOS-only — it renders as a plain View on
// Android, so content sits under the status bar and gesture nav. Always take it
// from react-native-safe-area-context (see docs/ui-playbook.md).
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useRouter, useLocalSearchParams, type Href } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useTabBarInset } from "@/hooks/useTabBarInset";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { formatPrice, formatDualPrice } from "@/lib/format";
import { useSettings as useSettingsHook } from "@/lib/settings";
import { useTranslation } from "react-i18next";
// InboxHeaderButton and ThemeToggleButton moved to MarketplacePageHeader
import { CATEGORIES } from "@/data/categories";
import { collectorsApi } from "@/api/collectorsApi";
import { dataProvider, type Item as DataItem, type PublicUserProfile } from "@/data";
import { COMMUNITY_GATED } from "@/config/featureFlags";
import { useToast } from "@/components/Toast";
import { fireHaptic, HapticIntent } from "@/haptics";
import logger from "@/utils/logger";
import { track } from '@/analytics/track';
import { MarketplaceSearchBar } from '@/components/MarketplaceSearchBar';
import { MarketplaceFilterPanel } from '@/components/MarketplaceFilterPanel';
import { SearchResultQuickView } from '@/components/SearchResultQuickView';
import { SkeletonList } from '@/components/Skeleton';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { MarketplacePageHeader } from '@/components/marketplace/MarketplacePageHeader';
import { MarketplaceResultCard, type MarketplaceResultItem } from '@/components/marketplace/MarketplaceResultCard';
import { MarketplaceEmptyState } from '@/components/marketplace/MarketplaceEmptyState';
import { DemandHeatBanner } from '@/components/marketplace/DemandHeatBanner';
import { AdBanner } from '@/components/ads/AdBanner';
import { RegionalInsightsSection } from '@/components/marketplace/RegionalInsightsSection';
import { MarketMoversSection } from '@/components/marketplace/MarketMoversSection';
import {
  listListings,
  listOffers,
  countOffersNeedingAction,
  type P2PListing,
  type P2POffer,
} from '@/api/p2pApi';
import { useAuthContext } from '@/providers/useAuthContext';
import { text as textToken, fontWeight } from '@/theme/tokens';
import type { CurrencyCode } from '@/data/types';

// --- Types for marketplace API results ---
type MarketplaceHit = {
  source: string;
  title: string;
  price: number | null;
  currency: string;
  source_price: number | null;
  source_currency: string | null;
  url: string;
  affiliate_url: string | null;
  affiliate_source: string | null;
  image_url: string | null;
  condition: string | null;
  is_sold: boolean;
  provenance_score: number;
  source_reliability: number;
  recency_score: number;
  shipping_cost: number | null;
  ships_from: string | null;
  domestic_only: boolean;
  listing_region: string | null;
  shipping_estimate: {
    min_eur: number;
    max_eur: number;
    exact_eur: number | null;
    is_domestic: boolean;
    disclaimer: string | null;
  } | null;
};

// Unified result type for rendering (same visual as before)
type SearchResult = {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  // External marketplace data (when result is from API)
  isMarketplace?: boolean;
  externalUrl?: string;
  affiliateUrl?: string;
  source?: string;
  condition?: string;
  // Image
  image_url?: string | null;
  // Shipping & cross-border
  domesticOnly?: boolean;
  shippingHint?: string;
  secondaryPrice?: string | null;
  sourceCurrency?: string | null;
};

// Recent searches REMOVED 2026-08-08, matching app/search.tsx (removed
// 2026-08-07). The key is cleared once on mount rather than abandoned: an
// orphaned key keeps a user's search history on the device indefinitely after
// the feature that justified collecting it is gone, which is the kind of quiet
// data retention a privacy policy should not have to cover.
const LEGACY_RECENT_SEARCHES_KEY = "collectai_recent_searches";

// BROWSE_CATEGORIES moved to app/search.tsx with the browse grid (2026-08-11).

// Filter options (constants moved to MarketplaceFilterPanel component)

// Tile colors now come from theme.tileScale (Tiffany brand scale)

// Compute uniform tile dimensions for 2-col grid
const SCREEN_WIDTH = Dimensions.get("window").width;
const TILE_PAD = 16; // matches content paddingHorizontal
const TILE_GAP = 12;
const TILE_WIDTH = Math.floor((SCREEN_WIDTH - TILE_PAD * 2 - TILE_GAP) / 2);
const TILE_HEIGHT = Math.floor(TILE_WIDTH * 0.62); // ~110-120px for consistent aspect

const SearchScreen: React.FC = () => {
  const router = useRouter();
  const { colors, isDark } = useAppTheme();
  // ExternalTabBar is absolute at the root stack and reserves no layout space,
  // so a literal paddingBottom here draws the last row under the bar. Derive it.
  const bottomInset = useTabBarInset();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettingsHook();
  const { t } = useTranslation();
  const { showToast } = useToast();
  // Seeded from `?q=`, which `MarketplacePricesSection`'s "See all N results"
  // link has always sent and this screen never read — so that link landed on an
  // empty marketplace and the user retyped the name they had just tapped. A lazy
  // initialiser, not an effect: params are there on the first render, and an
  // effect that wrote `query` while depending on it is the offers.tsx bug
  // (scripts/check-self-cancelling-effects.mjs).
  const { q: initialQuery } = useLocalSearchParams<{ q?: string }>();
  const [query, setQuery] = useState(() => (typeof initialQuery === 'string' ? initialQuery : ''));
  const [searchLoading, setSearchLoading] = useState(false);
  // Escalating status copy for the live aggregation. Marketplace search
  // hits 44 adapters server-side and can legitimately take 30-60 s. A
  // silent skeleton at that length feels broken, so the status text
  // updates at 0 / 6 / 20 / 45 s.
  const [searchStatus, setSearchStatus] = useState<string>('');
  const [refreshing, setRefreshing] = useState(false);
  const [marketplaceResults, setMarketplaceResults] = useState<SearchResult[]>([]);
  const [collectionResults, setCollectionResults] = useState<SearchResult[]>([]);
  // DISABLED pre-launch: the external "Buy externally" search does a live scrape
  // across 44 marketplace adapters, which can take up to 90s for rare items and
  // reads as broken. Only the instant local sections (Your items + Categories)
  // run while this is false. Flip to true once the scrape budget is fast enough.
  const EXTERNAL_MARKETPLACE_SEARCH_ENABLED = false;
  const searchIdRef = useRef(0);

  // Escalating status copy while marketplace search is running. The server
  // live-aggregates across 44 adapters; 30-60s is common for rare items.
  // We update the visible status text at 0 / 6 / 20 / 45 s so the spinner
  // never feels frozen. Timers are cleared as soon as `searchLoading` flips
  // back to false.
  useEffect(() => {
    if (!searchLoading) {
      setSearchStatus('');
      return;
    }
    // External scrape disabled → only the fast local search runs; show a brief
    // neutral status and skip the long-wait ("up to 90s") escalation entirely.
    if (!EXTERNAL_MARKETPLACE_SEARCH_ENABLED) {
      setSearchStatus('Searching…');
      return;
    }
    setSearchStatus('Searching marketplaces…');
    const t1 = setTimeout(() => setSearchStatus('Aggregating across 44 sources…'), 6_000);
    const t2 = setTimeout(() => setSearchStatus('Still searching — this can take up to 90s for rare items.'), 20_000);
    const t3 = setTimeout(() => setSearchStatus('Almost there…'), 45_000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [searchLoading, EXTERNAL_MARKETPLACE_SEARCH_ENABLED]);

  // User search state
  const [userSearchVisible, openUserSearch, closeUserSearch] = useModal();
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userSearchResults, setUserSearchResults] = useState<PublicUserProfile[]>([]);
  const [userSearchLoading, setUserSearchLoading] = useState(false);
  const [quickViewItem, setQuickViewItem] = useState<SearchResult | null>(null);
  const [quickViewVisible, openQuickView, closeQuickView] = useModal();
  const [demandHeat, setDemandHeat] = useState<{ item_key: string; title: string; category: string; demand_score: number; search_count: number }[]>([]);
  const [regionalDemand, setRegionalDemand] = useState<{ item_key: string; category: string; signal_count: number; region: string }[]>([]);
  const debouncedUserQuery = useDebounce(userSearchQuery.trim(), 350);

  useEffect(() => {
    let cancelled = false;
    const DEMAND_HEAT_CACHE_KEY = '@demand_heat_cache';
    const REGIONAL_DEMAND_CACHE_KEY = '@regional_demand_cache';
    const CACHE_TTL = 15 * 60 * 1000; // 15 minutes

    async function fetchDemandHeat() {
      try {
        const cached = await AsyncStorage.getItem(DEMAND_HEAT_CACHE_KEY);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL) {
            if (!cancelled && Array.isArray(data) && data.length) setDemandHeat(data);
            return;
          }
        }
      } catch (e) {
        logger.error('[silent-catch] marketplace.tsx:207:', e); /* cache miss, proceed to fetch */ }
      try {
        const data = await collectorsApi.getDemandHeat();
        if (cancelled) return;
        const resp = data as { items?: { item_key: string; title: string; category: string; demand_score: number; search_count: number }[] } | undefined;
        const items = resp?.items;
        if (Array.isArray(items) && items.length) {
          const sliced = items.slice(0, 6);
          setDemandHeat(sliced);
          AsyncStorage.setItem(DEMAND_HEAT_CACHE_KEY, JSON.stringify({ data: sliced, ts: Date.now() })).catch(() => {});
        }
      } catch (err) { logger.error('[Marketplace] getDemandHeat error:', err); }
    }

    async function fetchRegionalDemand() {
      try {
        const cached = await AsyncStorage.getItem(REGIONAL_DEMAND_CACHE_KEY);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL) {
            if (!cancelled && Array.isArray(data)) setRegionalDemand(data);
            return;
          }
        }
      } catch (e) {
        logger.error('[silent-catch] marketplace.tsx:231:', e); /* cache miss, proceed to fetch */ }
      try {
        const data = await collectorsApi.getDemandHeatByRegion();
        if (cancelled) return;
        const resp = data as { items?: { item_key: string; category: string; signal_count: number; region: string }[] } | undefined;
        if (Array.isArray(resp?.items)) {
          const sliced = resp!.items.slice(0, 5);
          setRegionalDemand(sliced);
          AsyncStorage.setItem(REGIONAL_DEMAND_CACHE_KEY, JSON.stringify({ data: sliced, ts: Date.now() })).catch(() => {});
        }
      } catch (err) { logger.error('[Marketplace] getDemandHeatByRegion error:', err); }
    }

    fetchDemandHeat();
    fetchRegionalDemand();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!debouncedUserQuery) {
      setUserSearchResults([]);
      setUserSearchLoading(false);
      return;
    }
    let cancelled = false;
    setUserSearchLoading(true);
    dataProvider.searchUsers(debouncedUserQuery).then((results) => {
      if (!cancelled) {
        setUserSearchResults(results);
        setUserSearchLoading(false);
      }
    }).catch((err) => {
      logger.warn("[UserSearch] error:", err);
      if (!cancelled) {
        setUserSearchResults([]);
        setUserSearchLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [debouncedUserQuery]);

  const handleOpenUserProfile = useCallback((userId: string) => {
    closeUserSearch();
    setUserSearchQuery("");
    setUserSearchResults([]);
    router.push(`/users/${userId}`);
  }, [router, closeUserSearch]);

  // Filter state
  const [filterVisible, openFilter, closeFilter] = useModal();
  const [filterSources, setFilterSources] = useState<string[]>([]);
  const [filterConditions, setFilterConditions] = useState<string[]>([]);
  const [filterMinPrice, setFilterMinPrice] = useState("");
  const [filterMaxPrice, setFilterMaxPrice] = useState("");
  const [filterSort, setFilterSort] = useState("relevance");

  // Trending-categories fetch removed 2026-07-24. The rail it fed was deleted
  // from the render (see "Trending categories removed" below), so this effect
  // called /insights/personalized on every mount and wrote the result into
  // state no JSX read — the endpoint's four computed arrays were all discarded.
  // The concentration/diversification half of that payload now renders on the
  // analytics screen; see app/analytics.tsx "Concentration & Balance" and the
  // seam fn in src/data/personalizedInsights.ts. Restore a call here only
  // alongside a rail that actually renders it.

  // Count of active filters for badge
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filterSources.length > 0) count++;
    if (filterConditions.length > 0) count++;
    if (filterMinPrice || filterMaxPrice) count++;
    if (filterSort !== "relevance") count++;
    return count;
  }, [filterSources, filterConditions, filterMinPrice, filterMaxPrice, filterSort]);

  // One-shot cleanup of the retired recent-searches key. Not a load.
  useEffect(() => {
    AsyncStorage.removeItem(LEGACY_RECENT_SEARCHES_KEY).catch(() => {});
  }, []);

  /*
   * Member listings for the rail (2026-08-10).
   *
   * The member marketplace used to be a single grey link-row identical to the
   * one beside it, so it read as a settings entry rather than as a place to buy.
   * A rail of real photos and prices IS the marketplace; a row only describes
   * one.
   *
   * `null` means "not loaded yet" and is deliberately distinct from `[]`
   * ("loaded, nothing listed") — the render below falls back to the plain row
   * when there is genuinely nothing to show, because an empty rail would be
   * worse than the link it replaced. Same reasoning as the segment that was
   * removed from app/listings.tsx on 2026-08-07: never show a member a shelf
   * for something that does not exist.
   */
  const [memberListings, setMemberListings] = useState<P2PListing[] | null>(null);
  const { loading: authLoading, session } = useAuthContext();

  /** Member listings matching the CURRENT query — distinct from `memberListings`,
   *  which is the unfiltered rail shown when no query is typed. */
  const [memberResults, setMemberResults] = useState<P2PListing[]>([]);

  /*
   * Open bids on the marketplace overview (restored 2026-08-11).
   *
   * Removed the previous day because it sat in an identical grey `memberMarketRow`
   * beside the marketplace row and read as a settings entry. Removing it was the
   * wrong correction: the badged icon on app/listings.tsx is one screen deeper,
   * so the OVERVIEW had no route to your own negotiations at all.
   *
   * Back, but earning its place — it shows the actual state (how many buying,
   * how many selling, how many need you) in the semantic colours from the
   * buy/sell treatment, instead of a chevron and a noun.
   */
  const [offers, setOffers] = useState<P2POffer[] | null>(null);

  useEffect(() => {
    // Don't fire before the session exists. `/p2p/listings` is authed, so a
    // fetch during auth hydration 401s — proven on the simulator 2026-08-10,
    // which logged this twelve times behind the login screen before anyone had
    // signed in. Exactly the rule in CLAUDE.md "Loading states" §2, and the same
    // class as the watchlist bug fixed the same day: a request fired too early
    // does not fail loudly, it just leaves the surface empty.
    //
    // No deadline needed here, unlike the watchlist gate: this is an enrichment
    // with a fallback (the link row) rather than the screen's primary content,
    // so a wedged session degrades instead of pinning a skeleton.
    if (authLoading || !session) return;
    let cancelled = false;
    // Open bids, same auth gate and same reason as the rail below.
    listOffers('all')
      .then((res) => { if (!cancelled) setOffers(res?.offers ?? []); })
      .catch((err) => {
        logger.error('[Marketplace] open bids unavailable:', err);
        if (!cancelled) setOffers([]);
      });
    listListings({ sort: 'newest', limit: 10 })
      .then((res) => {
        if (!cancelled) setMemberListings(res?.listings ?? []);
      })
      .catch((err) => {
        // logger.error, not warn: warn is stripped from release builds
        // (CLAUDE.md), and a silently missing marketplace rail on TestFlight is
        // exactly the build where it matters. Falls back to the link row.
        logger.error('[Marketplace] member listings rail unavailable:', err);
        if (!cancelled) setMemberListings([]);
      });
    return () => { cancelled = true; };
  }, [authLoading, session]);

  const trimmedQuery = query.trim();
  const debouncedQuery = useDebounce(trimmedQuery, 350);

  // Category matches — instant, local (CATEGORIES is static), so searching
  // "taylor swift" surfaces the category immediately even before the
  // marketplace/collection network searches return. Matches name, id (with
  // underscores treated as spaces), and tagline.
  const categoryResults = useMemo(() => {
    if (!trimmedQuery) return [];
    const q = trimmedQuery.toLowerCase();
    return CATEGORIES.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.id.replace(/_/g, ' ').toLowerCase().includes(q) ||
        (c.tagline ?? '').toLowerCase().includes(q),
    ).slice(0, 6);
  }, [trimmedQuery]);


  // Unique collections from collection results only
  const uniqueCollections = useMemo(
    () =>
      Array.from(
        new Map(
          collectionResults
            .filter((r) => r.collectionName && r.collectionName !== "-")
            .map((item) => [item.collectionName, item])
        ).values()
      ),
    [collectionResults]
  );

  // Run the actual search against marketplace API + local collection
  const executeSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setMarketplaceResults([]);
      setCollectionResults([]);
      return;
    }

    const searchId = ++searchIdRef.current;
    setSearchLoading(true);

    // Build filter options for marketplace API
    const searchOpts: Parameters<typeof collectorsApi.marketplaceSearch>[1] = {};
    if (filterSources.length > 0) searchOpts.source = filterSources;
    if (filterConditions.length > 0) searchOpts.condition = filterConditions;
    if (filterMinPrice) {
      const val = parseFloat(filterMinPrice);
      if (!isNaN(val)) searchOpts.min_price = val;
    }
    if (filterMaxPrice) {
      const val = parseFloat(filterMaxPrice);
      if (!isNaN(val)) searchOpts.max_price = val;
    }
    if (filterSort && filterSort !== "relevance") searchOpts.sort = filterSort;
    if (settings.region) searchOpts.region = settings.region;

    // Run marketplace API + local collection search in parallel. The external
    // marketplace scrape is gated off pre-launch (see flag above) — when
    // disabled it resolves to null instantly so only the fast local "Your items"
    // + instant "Categories" sections populate.
    // Member listings are searched ALONGSIDE the two existing sources
    // (2026-08-10). docs/P2P_MARKETPLACE_SPEC.md §2 Stage 1 says buyer discovery
    // is "listings appear in search, on the catalog item page, and as
    // market_hits rows", and build-order item 6 is "Listings surfaced in search
    // + catalog item page" — that item was never built, so searching for an item
    // a member had listed returned nothing from the member marketplace.
    //
    // Server-side this is an ILIKE on the listing title with LIKE metacharacters
    // escaped, restricted to `delisted_at IS NULL AND status = 'active'`
    // (p2p_listing_router.py:1059) — so results are only what is genuinely FOR
    // SALE right now. Sold and delisted never appear.
    //
    // Third element of the SAME Promise.allSettled rather than a separate
    // effect: it shares the `searchId` stale-guard below, so a slow member
    // search cannot overwrite the results of a newer query.
    const [mktResult, colResult, memResult] = await Promise.allSettled([
      EXTERNAL_MARKETPLACE_SEARCH_ENABLED
        ? collectorsApi.marketplaceSearch(q.trim(), searchOpts).catch((err: unknown) => {
            logger.warn("[Search] marketplace search error:", err);
            return null;
          })
        : Promise.resolve(null),
      dataProvider.searchItems(q.trim()).catch((err: unknown) => {
        logger.warn("[Search] collection search error:", err);
        return [] as DataItem[];
      }),
      listListings({ q: q.trim(), limit: 10, sort: 'newest' }).catch((err: unknown) => {
        // logger.error, not warn — warn is stripped from release builds, and a
        // member's listing silently missing from search is exactly the failure
        // that must leave a trace on TestFlight.
        logger.error("[Search] member listing search error:", err);
        return null;
      }),
    ]);

    // Stale response guard
    if (searchId !== searchIdRef.current) return;

    // Map marketplace hits
    const mktData = (mktResult.status === "fulfilled" ? mktResult.value : null) as { hits?: MarketplaceHit[] } | null;
    const hits: MarketplaceHit[] = mktData?.hits ?? [];
    const mktResults: SearchResult[] = hits
      .filter((h) => !h.is_sold)
      .slice(0, 10)
      .map((h, i) => {
        // Build shipping hint
        let shippingHint: string | undefined;
        const est = h.shipping_estimate;
        if (est) {
          if (est.exact_eur != null) {
            shippingHint = est.exact_eur === 0
              ? "+Free shipping"
              : `+${formatPrice(est.exact_eur)} shipping`;
          } else {
            shippingHint = `+${formatPrice(est.min_eur)}-${formatPrice(est.max_eur)} est. shipping`;
          }
        }

        // Build secondary price (original currency)
        let secondaryPrice: string | null = null;
        if (h.price != null && h.source_currency && h.source_currency !== settings.currency) {
          const dual = formatDualPrice(h.price, h.source_currency, settings);
          secondaryPrice = dual.secondary;
        }

        return {
          id: `mkt_${i}_${h.url}`,
          name: h.title || "Untitled",
          category: h.source || "",
          collectionName: h.condition || "-",
          value: h.price ?? 0,
          isMarketplace: true,
          externalUrl: h.url,
          affiliateUrl: h.affiliate_url ?? undefined,
          source: h.source,
          condition: h.condition ?? undefined,
          image_url: h.image_url,
          domesticOnly: h.domestic_only,
          shippingHint,
          secondaryPrice,
          sourceCurrency: h.source_currency,
        };
      });

    // Map collection items
    const colData = colResult.status === "fulfilled" ? colResult.value : [];
    const colResults: SearchResult[] = (colData ?? []).slice(0, 10).map((item) => ({
      id: item.id,
      name: item.name,
      category: item.category,
      collectionName: (item.collections ?? [])[0] ?? "-",
      value: item.price ?? item.priceBand?.q50 ?? 0,
    }));

    // Notify user about search failures
    if (mktResult.status === 'rejected' && colResult.status === 'rejected') {
      showToast({ message: 'Could not reach the marketplace. Check your connection and try again.', type: 'error' });
    } else if (mktResult.status === 'rejected') {
      showToast({ message: 'Marketplace search failed — showing collection results only.', type: 'info' });
    } else if (colResult.status === 'rejected') {
      showToast({ message: 'Collection search failed — showing marketplace results only.', type: 'info' });
    }

    // Member listings matching the query. No toast on failure: this is additive
    // to a search that still returned its other two sources, and telling someone
    // their search failed because an enrichment did would be false. The
    // logger.error above is the trace.
    const memData = (memResult.status === 'fulfilled' ? memResult.value : null) as { listings?: P2PListing[] } | null;
    setMemberResults(memData?.listings ?? []);

    setMarketplaceResults(mktResults);
    setCollectionResults(colResults);
    setSearchLoading(false);
    track({ name: 'marketplace_search', properties: { query: q, result_count: mktResults.length } });
    setRefreshing(false);
  }, [filterSources, filterConditions, filterMinPrice, filterMaxPrice, filterSort, settings]);

  // Auto-search when debounced query changes (avoids firing on every keystroke)
  useEffect(() => {
    if (debouncedQuery) {
      executeSearch(debouncedQuery);
    } else {
      setMarketplaceResults([]);
      setCollectionResults([]);
      setMemberResults([]);
    }
  }, [debouncedQuery, executeSearch]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    if (trimmedQuery) {
      executeSearch(trimmedQuery);
    } else {
      setRefreshing(false);
    }
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
  }, [trimmedQuery, executeSearch, settings.hapticsEnabled]);

  /*
   * Submitting the search bar hands the query to the UNIFIED search (2026-08-10).
   *
   * Typing still searches in place — the debounced `executeSearch` above keeps
   * showing your items, categories and member listings as you type. But pressing
   * search means "find me this thing", and only unified search can answer that:
   * it is the one query path that reads `category_items`, so it is the only one
   * that can find a Rolex Daytona among the 140k catalogue rows. This screen's
   * own search never touches the catalogue, which is why that query came back
   * empty while the catalogue held 77 Rolexes.
   *
   * Routed to `/search`, NOT `/(tabs)/search`. Both render the same component,
   * but `npm run check:params` resolves a push target to its route FILE, and the
   * tab file is a one-line re-export containing no `useLocalSearchParams` — so
   * pushing there reported "that route reads: (none)" and the gate could not
   * prove `q` is consumed. `app/search.tsx` reads it directly, so the contract
   * is checkable. The screen renders its own QuickNavBar, so it keeps its
   * navigation outside the tabs navigator.
   */
  const handleSubmitSearch = useCallback(() => {
    if (!trimmedQuery) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({ pathname: '/search', params: { q: trimmedQuery } });
  }, [trimmedQuery, router, settings.hapticsEnabled]);

  // Runs a search from a tapped chip — the demand-heat banner and the
  // regional-insights row use it. (Popular Searches used it too, until that
  // section was removed; those two are the only callers now.)
  const handleChipPress = useCallback((term: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setQuery(term);
    executeSearch(term);
  }, [executeSearch, settings.hapticsEnabled]);

  const handleOpenResult = useCallback((item: SearchResult) => {
    if (item.domesticOnly) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (item.isMarketplace) {
      setQuickViewItem(item);
      openQuickView();
    } else {
      router.push({
        pathname: "/item/[id]",
        params: {
          id: item.id,
          name: item.name,
          category: item.category,
          collectionName: item.collectionName,
          value: String(item.value),
        },
      });
    }
  }, [router, settings.hapticsEnabled]);

  const handleQuickViewOpen = useCallback(() => {
    if (!quickViewItem) return;
    const openUrl = quickViewItem.affiliateUrl || quickViewItem.externalUrl;
    if (openUrl) {
      Linking.openURL(openUrl).catch((err) => {
        logger.warn('[Marketplace] Failed to open URL', err);
      });
    }
    closeQuickView();
    setQuickViewItem(null);
  }, [quickViewItem, closeQuickView]);

  const handleQuickViewShare = useCallback(async () => {
    if (!quickViewItem) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      await Share.share({
        message: `${quickViewItem.name} - ${formatPrice(quickViewItem.value)} on ${quickViewItem.source || 'Marketplace'}`,
        url: quickViewItem.externalUrl,
      });
    } catch (err) {
      logger.error('[Marketplace] share error:', err);
    }
  }, [quickViewItem, settings.hapticsEnabled]);

  const handleOpenCategory = useCallback((categoryId: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/categories/${encodeURIComponent(categoryId)}`);
  }, [router, settings.hapticsEnabled]);

  const handleOpenCollection = useCallback((collectionName: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({
      pathname: "/(tabs)/items",
      params: { collectionName },
    });
  }, [router, settings.hapticsEnabled]);

  const handleFilterApply = useCallback(() => {
    closeFilter();
    if (trimmedQuery) executeSearch(trimmedQuery);
  }, [closeFilter, trimmedQuery, executeSearch]);

  const handleFilterReset = useCallback(() => {
    setFilterSources([]);
    setFilterConditions([]);
    setFilterMinPrice("");
    setFilterMaxPrice("");
    setFilterSort("relevance");
  }, []);

  const handleCloseUserSearch = useCallback(() => {
    closeUserSearch();
    setUserSearchQuery("");
    setUserSearchResults([]);
  }, [closeUserSearch]);

  const handleClearUserSearch = useCallback(() => {
    setUserSearchQuery("");
    setUserSearchResults([]);
  }, []);

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === "ios" ? 50 : 0}
      >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          { backgroundColor: colors.background, paddingBottom: bottomInset },
        ]}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      >
        <Animated.View style={animatedStyle}>
        {/* Header */}
        <MarketplacePageHeader />

        {/* Search input + filter button */}
        <MarketplaceSearchBar
          theme={colors}
          query={query}
          onQueryChange={setQuery}
          onSubmit={handleSubmitSearch}
          onOpenFilter={openFilter}
          activeFilterCount={activeFilterCount}
        />

        {/* Ad slot — invisible until FEATURE_ADS is enabled */}
        <AdBanner placement="marketplace_banner" />

        {/* Find Collectors button — gated until community has density.
            With <50 public profiles, the modal returns 0 results for any
            non-trivial query and looks broken. Hidden via COMMUNITY_GATED;
            modal still mounts via deep-link if a future entry surfaces it. */}
        {!trimmedQuery && !COMMUNITY_GATED && (
          <AnimatedPressable
            style={[styles.findCollectorsButton, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
            onPress={openUserSearch}
            accessibilityRole="button"
            accessibilityLabel={t('marketplace.find_collectors_a11y')}
          >
            <Ionicons name="people-outline" size={18} color={colors.accent} />
            <Text style={[styles.findCollectorsText, { color: colors.accent }]}>{t('marketplace.find_collectors')}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </AnimatedPressable>
        )}

        {/* Member marketplace entry — P2P Stage 1.
            Placed above Browse by category because buying intent is highest
            before a query is typed, and because a seller needs to SEE that
            selling happens here: sellers list where they believe buyers are.
            Links out to a dedicated screen rather than embedding a grid —
            this file is 1,266 lines and its own external search is disabled
            pre-launch. See docs/P2P_MARKETPLACE_SPEC.md. */}
        {!trimmedQuery && (
          memberListings && memberListings.length > 0 ? (
            <View style={styles.memberRailWrap}>
              <View style={styles.memberRailHead}>
                <Text style={[styles.memberRailTitle, { color: colors.text }]}>Member marketplace</Text>
                <AnimatedPressable
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    router.push('/listings' as Href);
                  }}
                  hitSlop={8}
                  accessibilityRole="link"
                  accessibilityLabel="See all member listings"
                >
                  <Text style={[styles.memberRailSeeAll, { color: colors.accent }]}>See all →</Text>
                </AnimatedPressable>
              </View>
              <FlatList
                horizontal
                data={memberListings}
                keyExtractor={(l) => l.id}
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.memberRailList}
                renderItem={({ item: l }) => (
                  <AnimatedPressable
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      router.push({ pathname: '/listing/[id]', params: { id: l.id } });
                    }}
                    style={[styles.memberRailCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={`${l.title}, ${formatPrice(l.price, (l.currency as CurrencyCode) || 'EUR', settings.numberLocale)}${l.seller_name ? `, from ${l.seller_name}` : ''}`}
                  >
                    {l.image_url ? (
                      <Image
                        source={{ uri: l.image_url }}
                        style={styles.memberRailImg}
                        contentFit="cover"
                        transition={120}
                      />
                    ) : (
                      <View style={[styles.memberRailImg, styles.memberRailImgEmpty, { backgroundColor: colors.accent + '12' }]}>
                        <Ionicons name="image-outline" size={20} color={colors.muted} />
                      </View>
                    )}
                    {/* A catalog image is a STOCK photo, not the seller's item.
                        Labelled because condition is the one thing a
                        second-hand buyer cannot judge from stock art — see the
                        `image_is_catalog` note in src/api/p2pApi.ts. */}
                    {l.image_is_catalog ? (
                      <View style={[styles.memberRailStock, { backgroundColor: colors.background + 'E6' }]}>
                        <Text style={[styles.memberRailStockText, { color: colors.muted }]}>Stock photo</Text>
                      </View>
                    ) : null}
                    <Text numberOfLines={2} style={[styles.memberRailName, { color: colors.text }]}>
                      {l.title}
                    </Text>
                    <Text style={[styles.memberRailPrice, { color: colors.text }]}>
                      {formatPrice(l.price, (l.currency as CurrencyCode) || 'EUR', settings.numberLocale)}
                    </Text>
                  </AnimatedPressable>
                )}
              />
            </View>
          ) : (
            /* Nothing listed yet (or the fetch failed) — keep the plain row so
               the surface still explains itself and invites the first listing.
               An empty rail would be a worse signal than a link. */
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/listings' as Href);
              }}
              style={[styles.memberMarketRow, { backgroundColor: colors.card, borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Browse member listings"
            >
              <View style={[styles.memberMarketIcon, { backgroundColor: colors.accent + '18' }]}>
                <Ionicons name="pricetags-outline" size={18} color={colors.accent} />
              </View>
              <View style={styles.memberMarketText}>
                <Text style={[styles.memberMarketTitle, { color: colors.text }]}>Member marketplace</Text>
                <Text style={[styles.memberMarketSub, { color: colors.muted }]}>
                  Buy from other collectors — or list something you own
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </AnimatedPressable>
          )
        )}

        {/* Open bids — RESTORED 2026-08-11 after being removed the day before.
            Removing it was the wrong correction: the badged icon on
            app/listings.tsx is a screen deeper, so the marketplace OVERVIEW had
            no route to your own negotiations at all.
            It earns its place now by showing state rather than a noun — how many
            you are buying, how many selling, how many need you — in the same
            semantic colours as the offers screen (info = buying, success =
            selling). Body copy at `md`, per docs/ui-playbook.md. */}
        {!trimmedQuery && offers && offers.length > 0 && (() => {
          const buying = offers.filter((o) => o.i_am_buyer).length;
          const selling = offers.length - buying;
          const needsMe = countOffersNeedingAction(offers);
          return (
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/offers' as Href);
              }}
              style={[styles.bidsRow, {
                backgroundColor: colors.card,
                borderColor: needsMe > 0 ? colors.accent : colors.border,
              }]}
              accessibilityRole="button"
              accessibilityLabel={
                `Open bids: ${buying} buying, ${selling} selling` +
                (needsMe > 0 ? `, ${needsMe} waiting for you` : '')
              }
            >
              <View style={styles.bidsHead}>
                <Text style={[styles.bidsTitle, { color: colors.text }]}>Open bids</Text>
                {needsMe > 0 && (
                  <View style={[styles.bidsBadge, { backgroundColor: colors.accent }]}>
                    <Text style={[styles.bidsBadgeText, { color: colors.accentText }]}>
                      {needsMe} needs you
                    </Text>
                  </View>
                )}
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </View>
              <View style={styles.bidsCounts}>
                {buying > 0 && (
                  <View style={[styles.bidsPill, { backgroundColor: colors.infoBg }]}>
                    <Text style={[styles.bidsPillText, { color: colors.info }]}>
                      {buying} buying
                    </Text>
                  </View>
                )}
                {selling > 0 && (
                  <View style={[styles.bidsPill, { backgroundColor: colors.successBg }]}>
                    <Text style={[styles.bidsPillText, { color: colors.success }]}>
                      {selling} selling
                    </Text>
                  </View>
                )}
              </View>
            </AnimatedPressable>
          );
        })()}

        {/* Historical note (2026-08-10): this block briefly pointed at
            app/listings.tsx instead.

            It used to sit here, in an identical `memberMarketRow` directly
            beneath the member-marketplace row — and that was the problem. Two
            stacked grey rows with a chevron read as settings entries, not as a
            marketplace, so neither was findable. They are also not the same kind
            of thing: the marketplace row is DISCOVERY, open bids is your own
            in-flight negotiation state. Giving them equal visual weight on the
            discovery tab buried the discovery.

            The original comment here was right that /offers must not be
            reachable only from a notification — hence a segment on the listings
            screen rather than a deletion. Buying and negotiating over what you
            bought belong on the same screen. */}

        {/* Browse-by-category moved to the SEARCH tab 2026-08-11. Browsing a
            taxonomy is a search act, and it now lives where search does — this
            screen keeps the market signals (pulse, movers, regional). */}
        {!trimmedQuery && (
          <>
            {/* Market Pulse — demand heat */}
            <DemandHeatBanner items={demandHeat} onSearchItem={handleChipPress} />

            {/* Regional demand insights */}
            <RegionalInsightsSection items={regionalDemand} onSearchItem={handleChipPress} />

            {/* Market Movers — biggest 7d price gainers/losers (followed cats + see-all) */}
            <MarketMoversSection />

            {/* Trending categories removed */}
          </>
        )}

        {/* Filter bottom sheet */}
        <MarketplaceFilterPanel
          theme={colors}
          visible={filterVisible}
          filterSources={filterSources}
          filterConditions={filterConditions}
          filterMinPrice={filterMinPrice}
          filterMaxPrice={filterMaxPrice}
          filterSort={filterSort}
          onSetFilterSources={setFilterSources}
          onSetFilterConditions={setFilterConditions}
          onSetFilterMinPrice={setFilterMinPrice}
          onSetFilterMaxPrice={setFilterMaxPrice}
          onSetFilterSort={setFilterSort}
          onApply={handleFilterApply}
          onClose={closeFilter}
          onReset={handleFilterReset}
        />

        {/* User Search Modal */}
        <Modal
          visible={userSearchVisible}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={handleCloseUserSearch}
        >
          <SafeAreaView style={[styles.filterModal, { backgroundColor: colors.background }]}>
            {/* Header */}
            <View style={[styles.filterHeader, { borderBottomColor: colors.border }]}>
              <TouchableOpacity
                onPress={handleCloseUserSearch}
                accessibilityRole="button"
                accessibilityLabel={t('marketplace.close_user_search_a11y')}
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
              <Text style={[styles.filterHeaderTitle, { color: colors.text }]}>{t('marketplace.find_collectors')}</Text>
              <View style={{ width: 24 }} />
            </View>

            {/* Search input */}
            <View style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 }}>
              <View style={[styles.searchRow, { borderColor: colors.border }]}>
                <Ionicons name="search-outline" size={18} color={colors.muted} style={{ marginRight: 8 }} />
                <TextInput
                  value={userSearchQuery}
                  onChangeText={setUserSearchQuery}
                  placeholder={t('marketplace.search_users_placeholder')}
                  placeholderTextColor={colors.muted}
                  autoFocus
                  style={[styles.searchInput, { color: colors.text }]}
                  accessibilityLabel={t('marketplace.search_users_a11y')}
                  returnKeyType="search"
                />
                {userSearchQuery.length > 0 && (
                  <TouchableOpacity
                    onPress={handleClearUserSearch}
                    accessibilityRole="button"
                    accessibilityLabel={t('common.clear_search')}
                  >
                    <Ionicons name="close-circle" size={18} color={colors.muted} />
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Results */}
            {/* tab-bar-inset-ok: inside a pageSheet <Modal>, which presents
                above the root stack where ExternalTabBar lives — the bar is
                not over this list. */}
            <ScrollView
              style={{ flex: 1 }}
              contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
              keyboardShouldPersistTaps="handled"
            >
              {userSearchLoading && (
                <ActivityIndicator
                  size="small"
                  color={colors.accent}
                  style={{ marginTop: 24 }}
                />
              )}

              {!userSearchLoading && debouncedUserQuery.length > 0 && userSearchResults.length === 0 && (
                <View style={{ alignItems: "center", paddingTop: 32 }}>
                  <Ionicons name="people-outline" size={36} color={colors.muted} />
                  <Text style={[styles.noResultsTitle, { color: colors.text, marginTop: 12 }]}>
                    No collectors found
                  </Text>
                  <Text style={[styles.emptyText, { color: colors.muted }]}>
                    Try a different name or handle.
                  </Text>
                </View>
              )}

              {!userSearchLoading && userSearchResults.length > 0 && (
                <View style={{ marginTop: 8 }}>
                  <Text style={[styles.sectionTitle, { color: colors.muted, marginBottom: 8 }]}>
                    {userSearchResults.length} {userSearchResults.length === 1 ? "collector" : "collectors"} found
                  </Text>
                  {userSearchResults.map((user) => {
                    const initials = user.displayName
                      .split(" ")
                      .map((part) => part[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase() || "?";
                    return (
                      <AnimatedPressable
                        key={user.id}
                        style={[styles.userResultRow, { borderBottomColor: colors.border }]}
                        onPress={() => handleOpenUserProfile(user.id)}
                        accessibilityRole="button"
                        accessibilityLabel={`View profile of ${user.displayName}`}
                      >
                        {user.avatarUrl ? (
                          <View style={[styles.userAvatar, { backgroundColor: colors.accent + "20" }]}>
                            <Text style={[styles.userAvatarText, { color: colors.accent }]}>
                              {initials}
                            </Text>
                          </View>
                        ) : (
                          <View style={[styles.userAvatar, { backgroundColor: colors.accent + "20" }]}>
                            <Text style={[styles.userAvatarText, { color: colors.accent }]}>
                              {initials}
                            </Text>
                          </View>
                        )}
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.userResultName, { color: colors.text }]}>
                            {user.displayName}
                          </Text>
                          {user.handle && (
                            <Text style={[styles.userResultHandle, { color: colors.muted }]}>
                              @{user.handle}
                            </Text>
                          )}
                        </View>
                        <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                      </AnimatedPressable>
                    );
                  })}
                </View>
              )}

              {!userSearchLoading && !debouncedUserQuery && (
                <View style={{ alignItems: "center", paddingTop: 40 }}>
                  <Ionicons name="people-outline" size={40} color={colors.muted + "60"} />
                  <Text style={[styles.emptyText, { color: colors.muted, marginTop: 12 }]}>
                    Search for collectors by name or handle
                  </Text>
                </View>
              )}
            </ScrollView>
          </SafeAreaView>
        </Modal>

        {/* Results when searching */}
        {trimmedQuery ? (
          <View style={styles.section}>
            {/* Categories — instant local matches, shown above network results */}
            {categoryResults.length > 0 && (
              <>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Categories</Text>
                {categoryResults.map((cat) => (
                  <AnimatedPressable
                    key={cat.id}
                    style={[styles.catResultRow, { backgroundColor: colors.card, borderColor: colors.border }]}
                    onPress={() => handleOpenCategory(cat.id)}
                    accessibilityRole="button"
                    accessibilityLabel={`Open ${cat.name} category`}
                  >
                    <Ionicons name="grid-outline" size={18} color={colors.accent} />
                    <Text style={[styles.catResultName, { color: colors.text }]} numberOfLines={1}>{cat.name}</Text>
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </AnimatedPressable>
                ))}
              </>
            )}
            {searchLoading ? (
              <>
                {searchStatus ? (
                  <View style={styles.searchStatusRow}>
                    <ActivityIndicator size="small" color={colors.accent} />
                    <Text style={[styles.searchStatusText, { color: colors.muted }]}>
                      {searchStatus}
                    </Text>
                  </View>
                ) : null}
                <SkeletonList count={6} type="card" />
              </>
            ) : (
              <>
                {/* Your items — the user's own collection (internal) */}
                {collectionResults.length > 0 && (
                  <>
                    <Text style={[styles.sectionTitle, { color: colors.text }]}>Your items</Text>
                    {collectionResults.map((item) => (
                      <MarketplaceResultCard key={item.id} item={item} onPress={handleOpenResult} />
                    ))}
                  </>
                )}

                {/* From members — P2P listings matching the query.
                    Placed ABOVE "Buy externally" deliberately: these are items a
                    member can actually buy today, from another member, and the
                    external section is gated off pre-launch anyway. Only live
                    listings reach here — the server restricts browse to
                    `delisted_at IS NULL AND status = 'active'`. */}
                {memberResults.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: collectionResults.length > 0 ? 16 : 0 },
                      ]}
                    >
                      From members
                    </Text>
                    {memberResults.map((l) => (
                      <AnimatedPressable
                        key={l.id}
                        onPress={() => {
                          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                          router.push({ pathname: '/listing/[id]', params: { id: l.id } });
                        }}
                        style={[styles.memberHit, { backgroundColor: colors.card, borderColor: colors.border }]}
                        accessibilityRole="button"
                        accessibilityLabel={`${l.title}, ${formatPrice(l.price, (l.currency as CurrencyCode) || 'EUR', settings.numberLocale)}${l.seller_name ? `, from ${l.seller_name}` : ''}`}
                      >
                        {l.image_url ? (
                          <Image source={{ uri: l.image_url }} style={styles.memberHitImg} contentFit="cover" transition={120} />
                        ) : (
                          <View style={[styles.memberHitImg, styles.memberRailImgEmpty, { backgroundColor: colors.accent + '12' }]}>
                            <Ionicons name="image-outline" size={18} color={colors.muted} />
                          </View>
                        )}
                        <View style={styles.memberHitText}>
                          <Text numberOfLines={2} style={[styles.memberHitName, { color: colors.text }]}>
                            {l.title}
                          </Text>
                          <Text style={[styles.memberHitMeta, { color: colors.muted }]}>
                            {l.seller_name ? `${l.seller_name}` : 'Member listing'}
                            {l.condition_label ? ` · ${l.condition_label}` : ''}
                            {l.image_is_catalog ? ' · Stock photo' : ''}
                          </Text>
                        </View>
                        <Text style={[styles.memberHitPrice, { color: colors.text }]}>
                          {formatPrice(l.price, (l.currency as CurrencyCode) || 'EUR', settings.numberLocale)}
                        </Text>
                      </AnimatedPressable>
                    ))}
                  </>
                )}

                {/* Buy externally — live marketplace listings (external) */}
                {marketplaceResults.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: collectionResults.length > 0 ? 16 : 0 },
                      ]}
                    >
                      Buy externally
                    </Text>
                    {marketplaceResults.map((item) => (
                      <MarketplaceResultCard key={item.id} item={item} onPress={handleOpenResult} />
                    ))}
                  </>
                )}

                {/* Nothing matched in any of the FOUR sections. `memberResults`
                    was added 2026-08-10 and must be counted here — without it a
                    query that matched ONLY a member listing would render the
                    listing and the "no results" state at the same time. */}
                {categoryResults.length === 0 &&
                  collectionResults.length === 0 &&
                  memberResults.length === 0 &&
                  marketplaceResults.length === 0 && <MarketplaceEmptyState />}

                {/* Cross-border disclaimer */}
                {marketplaceResults.some((r) => r.shippingHint || r.secondaryPrice) && (
                  <Text style={[styles.crossBorderDisclaimer, { color: colors.muted }]}>
                    Customs/duties may apply for international purchases
                  </Text>
                )}

                {/* Collections section */}
                {uniqueCollections.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: 16 },
                      ]}
                    >
                      Collections
                    </Text>
                    {uniqueCollections.map((item) => (
                      <AnimatedPressable
                        key={item.collectionName}
                        style={styles.collectionRow}
                        onPress={() => handleOpenCollection(item.collectionName)}
                        accessibilityRole="button"
                        accessibilityLabel={`View ${item.collectionName} collection`}
                      >
                        <View style={[styles.collectionIcon, { backgroundColor: colors.accent + '10' }]}>
                          <Ionicons name="albums-outline" size={18} color={colors.accent} />
                        </View>
                        <View>
                          <Text
                            style={[styles.collectionTitle, { color: colors.text }]}
                          >
                            {item.collectionName}
                          </Text>
                          <Text
                            style={[styles.collectionMeta, { color: colors.muted }]}
                          >
                            {item.category}
                          </Text>
                        </View>
                      </AnimatedPressable>
                    ))}
                  </>
                )}
              </>
            )}
          </View>
        ) : null}
        </Animated.View>
      </ScrollView>
      </KeyboardAvoidingView>

      {/* Quick View Sheet */}
      <SearchResultQuickView
        theme={colors}
        visible={quickViewVisible}
        item={quickViewItem}
        onClose={() => { closeQuickView(); setQuickViewItem(null); }}
        onOpenUrl={handleQuickViewOpen}
        onShare={handleQuickViewShare}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
  },
  memberMarketRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderRadius: 16,
    padding: 12,
    marginBottom: 20,
  },
  // Open-bids entry. Semantic buy/sell colours, `md` body copy — nothing here
  // uses `xs`, which the playbook reserves for what no user needs to read.
  bidsRow: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 12,
    marginBottom: 20,
    gap: 8,
  },
  bidsHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  bidsTitle: {
    flex: 1,
    fontSize: textToken.lg,
    fontWeight: fontWeight.bold,
    letterSpacing: -0.2,
  },
  bidsBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  bidsBadgeText: {
    fontSize: textToken.sm,
    fontWeight: fontWeight.bold,
  },
  bidsCounts: {
    flexDirection: 'row',
    gap: 8,
  },
  bidsPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  bidsPillText: {
    fontSize: textToken.md,
    fontWeight: fontWeight.bold,
  },
  // Member-listing rail. Body copy starts at `md` per docs/ui-playbook.md
  // ("a new screen starts at md"); nothing here uses `xs`, which the playbook
  // reserves for things no user needs to read.
  memberRailWrap: {
    marginBottom: 20,
  },
  memberRailHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  memberRailTitle: {
    fontSize: textToken.lg,
    fontWeight: fontWeight.bold,
    letterSpacing: -0.2,
  },
  memberRailSeeAll: {
    fontSize: textToken.md,
    fontWeight: fontWeight.bold,
  },
  memberRailList: {
    gap: 12,
    paddingRight: 4,
  },
  memberRailCard: {
    width: 148,
    borderWidth: 1,
    borderRadius: 14,
    padding: 8,
    gap: 6,
  },
  memberRailImg: {
    width: '100%',
    height: 110,
    borderRadius: 10,
  },
  memberRailImgEmpty: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  memberRailStock: {
    position: 'absolute',
    top: 12,
    left: 12,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  memberRailStockText: {
    fontSize: textToken.sm,
    fontWeight: fontWeight.bold,
  },
  memberRailName: {
    fontSize: textToken.md,
    lineHeight: 18,
  },
  memberRailPrice: {
    fontSize: textToken.lg,
    fontWeight: fontWeight.bold,
  },
  // "From members" search-result row.
  memberHit: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderRadius: 14,
    padding: 10,
    marginBottom: 8,
  },
  memberHitImg: {
    width: 52,
    height: 52,
    borderRadius: 10,
  },
  memberHitText: {
    flex: 1,
    gap: 2,
  },
  memberHitName: {
    fontSize: textToken.md,
    fontWeight: fontWeight.bold,
    lineHeight: 18,
  },
  memberHitMeta: {
    fontSize: textToken.sm,
  },
  memberHitPrice: {
    fontSize: textToken.md,
    fontWeight: fontWeight.bold,
  },
  memberMarketIcon: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
  },
  memberMarketText: { flex: 1, gap: 2 },
  memberMarketTitle: { fontSize: 15, fontWeight: '700' },
  memberMarketSub: { fontSize: 12 },
  // (headerRow, headerLeft, headerTitle, headerSubtitle, headerIcons moved to MarketplacePageHeader)
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 4,
  },
  section: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 6,
  },
  catResultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 8,
  },
  catResultName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '600',
  },
  searchStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 4,
    marginBottom: 4,
  },
  searchStatusText: {
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: TILE_GAP,
  },
  categoryGridRow: {
    gap: TILE_GAP,
    marginBottom: TILE_GAP,
  },
  categoryTile: {
    width: TILE_WIDTH,
    height: TILE_HEIGHT,
    borderRadius: 12,
    padding: 12,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  categoryTileImage: {
    ...StyleSheet.absoluteFillObject,
  },
  categoryTileOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.42)",
  },
  categoryTileText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  // (resultRow, resultIcon, resultTitle, resultMeta, resultValue, resultSecondary, resultShipping, domesticBadge, domesticBadgeText moved to MarketplaceResultCard)
  crossBorderDisclaimer: {
    fontSize: 11,
    textAlign: "center",
    marginTop: 12,
    marginBottom: 4,
    fontStyle: "italic",
  },
  // (noResultsBlock moved to MarketplaceEmptyState)
  emptyText: {
    fontSize: 13,
    marginTop: 4,
    textAlign: "center",
  },
  noResultsTitle: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  collectionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  collectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  collectionTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  collectionMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  // (trending styles moved to TrendingCategoriesGrid component)
  // (search bar + filter button styles moved to MarketplaceSearchBar component)
  // (resultThumbnail, resultThumbnailPlaceholder moved to MarketplaceResultCard)
  filterModal: {
    flex: 1,
  },
  filterHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  filterHeaderTitle: {
    fontSize: 17,
    fontWeight: "700",
  },
  // (filter panel styles moved to MarketplaceFilterPanel component)
  // Find Collectors styles
  findCollectorsButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    marginBottom: 4,
  },
  findCollectorsText: {
    fontSize: 14,
    fontWeight: "700",
  },
  userResultRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  userAvatarText: {
    fontSize: 15,
    fontWeight: "700",
  },
  userResultName: {
    fontSize: 15,
    fontWeight: "600",
  },
  userResultHandle: {
    fontSize: 12,
    marginTop: 2,
  },
  // (quick view styles moved to SearchResultQuickView component)
  // (presetChipsSection, presetChipsRow, presetChip, presetChipText removed with
  //  the Popular Searches section — FilterSheet keeps its own presetChip styles)
  // (sectionSubtitle, demandCard, demandRank, demandRankText, demandTitle, demandMeta, demandScore, demandScoreText moved to DemandHeatBanner + RegionalInsightsSection)
});

function SearchScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchScreen />
    </ScreenErrorBoundary>
  );
}

export default SearchScreenWithBoundary;
