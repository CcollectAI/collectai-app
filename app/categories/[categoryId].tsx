/**
 * Category Store — Amazon Brand Store style layout for a category.
 * Shows: header, spotlight carousel, items, events, friends, sponsored slot.
 */
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  FlatList,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategoryStoreData, type Item, type CategoryMissingItem, type BuildPaintProject } from '@/data';
import { getCategoryById, getRelatedCategories } from '@/data/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { isBuildableCategory } from '@/constants/buildStepTemplates';
import { BETA_MODE } from '@/config/featureFlags';
import logger from '@/utils/logger';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { SkeletonList } from '@/components/Skeleton';
import MarketplacePickerSheet from '@/components/MarketplacePickerSheet';
import { collectorsApi } from '@/api/collectorsApi';
import { buildItemAffiliateUrl, openAffiliateUrl } from '@/utils/affiliateHelpers';
import { QuickNavBar } from '@/components/QuickNavBar';
import { radius, text, fontWeight } from '@/theme/tokens';
import { CatalogBrowseSection, type CatalogItemData } from '@/components/CatalogBrowseSection';
import {
  CategoryHeaderCard,
  SpotlightCarousel,
  CategoryItemsList,
  MangaSeriesProgress,
  MarketInsightsSection,
  MissingItemsChecklist,
  BuildProjectsSection,
  CategoryEventsSection,
  FriendsFollowSection,
  ExternalMarketplacesSection,
  RelatedCategoriesSection,
  SetProgressSection,
  FeaturedCollectionsSection,
  CategoryLeaderboardSection,
  CategoryTipsSection,
  CrossCategorySection,
  CategoryGradingGuide,
  NewReleasesSection,
} from '@/components/category';

function CategoryStoreScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [data, setData] = useState<CategoryStoreData | null>(null);
  const [missingItems, setMissingItems] = useState<CategoryMissingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [following, setFollowing] = useState(false);
  const [spotlightIndex, setSpotlightIndex] = useState(0);
  const [markingOwned, setMarkingOwned] = useState<string | null>(null);
  const [recentlyOwned, setRecentlyOwned] = useState<Set<string>>(new Set());

  // Shop sheet state for missing items
  const [shopMissingItem, setShopMissingItem] = useState<CategoryMissingItem | null>(null);
  const [shopSheetVisible, setShopSheetVisible] = useState(false);

  // Affiliate links for external marketplace buttons
  const [affiliateLinks, setAffiliateLinks] = useState<{ source: string; url: string; affiliate_url: string; label: string }[]>([]);

  // Market insights state
  const [deepDive, setDeepDive] = useState<Record<string, unknown> | null>(null);
  const [deepDiveLoading, setDeepDiveLoading] = useState(false);

  // Build projects state (for buildable categories)
  const [buildProjects, setBuildProjects] = useState<BuildPaintProject[]>([]);
  const [buildProjectsLoading, setBuildProjectsLoading] = useState(false);
  const isBuildable = categoryId ? isBuildableCategory(categoryId) : false;
  // Use app theme accent consistently; no per-category color overrides
  const accentColor = colors.accent;

  const [refreshing, setRefreshing] = useState(false);

  // ── Catalog Browser state ────────────────────────────────────────────
  const [catalogItems, setCatalogItems] = useState<CatalogItemData[]>([]);
  const [catalogTotal, setCatalogTotal] = useState(0);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogLoadingMore, setCatalogLoadingMore] = useState(false);
  const [catalogSearch, setCatalogSearch] = useState('');
  const [catalogOffset, setCatalogOffset] = useState(0);
  const [catalogExpanded, setCatalogExpanded] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const CATALOG_PAGE_SIZE = 30;

  const loadCatalogItems = useCallback(async (search: string, offset: number, append = false) => {
    if (!categoryId) return;
    if (offset === 0) setCatalogLoading(true);
    else setCatalogLoadingMore(true);

    try {
      const result = await collectorsApi.browseCatalogItems(categoryId, {
        q: search || undefined,
        limit: CATALOG_PAGE_SIZE,
        offset,
      });
      if (append) {
        setCatalogItems((prev) => [...prev, ...result.items]);
      } else {
        setCatalogItems(result.items);
      }
      setCatalogTotal(result.total);
      setCatalogOffset(offset + result.items.length);
    } catch (err: unknown) {
      logger.warn('[CategoryStore] catalog browse error:', err);
    } finally {
      setCatalogLoading(false);
      setCatalogLoadingMore(false);
      setCatalogLoaded(true);
    }
  }, [categoryId]);

  // Debounced catalog search
  const catalogSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up catalog search timer on unmount
  useEffect(() => {
    return () => {
      if (catalogSearchTimer.current) clearTimeout(catalogSearchTimer.current);
    };
  }, []);

  const handleCatalogSearchChange = (text: string) => {
    setCatalogSearch(text);
    if (catalogSearchTimer.current) clearTimeout(catalogSearchTimer.current);
    catalogSearchTimer.current = setTimeout(() => {
      setCatalogOffset(0);
      loadCatalogItems(text, 0, false);
    }, 400);
  };

  const handleCatalogLoadMore = () => {
    if (catalogLoadingMore || catalogLoading || catalogItems.length >= catalogTotal) return;
    loadCatalogItems(catalogSearch, catalogOffset, true);
  };

  // Load catalog when expanded (once)
  useEffect(() => {
    if (catalogExpanded && !catalogLoaded && !catalogLoading) {
      loadCatalogItems('', 0, false);
    }
  }, [catalogExpanded, catalogLoaded, catalogLoading, loadCatalogItems]);

  const spotlightRef = useRef<FlatList>(null);

  // Resolve category metadata for external marketplaces and related categories
  const categoryMeta = categoryId ? getCategoryById(categoryId) : undefined;
  const relatedCategories = categoryMeta ? getRelatedCategories(categoryMeta) : [];

  const loadCategoryData = useCallback(async () => {
    if (!categoryId) return;

    setError(null);

    try {
      const [storeResult, missingResult] = await Promise.all([
        dataProvider.getCategoryStore(categoryId),
        dataProvider.listCategoryMissing(categoryId).catch(() => []),
      ]);

      if (storeResult) {
        setData(storeResult);
        setMissingItems(missingResult);
      } else {
        setError('Category not found');
      }

      // Also reload deep dive and build projects
      dataProvider.getCategoryDeepDive(categoryId)
        .then(setDeepDive)
        .catch((err) => { logger.info('[Category] deep dive fetch error:', err); setDeepDive(null); });

      if (isBuildable) {
        dataProvider.listBuildPaintProjectsByCategory(categoryId)
          .then(setBuildProjects)
          .catch((err) => { logger.info('[Category] build projects fetch error:', err); setBuildProjects([]); });
      }
    } catch (err: unknown) {
      logger.warn('[CategoryStore] error:', err);
      setError((err as Error)?.message || 'Failed to load category');
    } finally {
      setLoading(false);
    }
  }, [categoryId, isBuildable]);

  useEffect(() => {
    if (!categoryId) return;
    setLoading(true);
    loadCategoryData();
  }, [categoryId, loadCategoryData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadCategoryData();
    setRefreshing(false);
  }, [loadCategoryData]);

  // Load follow state
  useEffect(() => {
    if (!categoryId) return;
    dataProvider.isFollowingCategory(categoryId)
      .then(setFollowing)
      .catch((err) => { logger.info('[Category] follow state fetch error:', err); });
  }, [categoryId]);

  // Deep dive and build projects are already fetched inside loadCategoryData() above.
  // No separate useEffects needed — they were duplicates.

  // Pre-fetch affiliate links for external marketplace section
  useEffect(() => {
    if (!categoryId || !categoryMeta) return;
    collectorsApi
      .getAffiliateLinks(categoryMeta.name, categoryId, 6, settings.region)
      .then((res) => setAffiliateLinks(res.links ?? []))
      .catch((err) => { logger.info('[Category] affiliate links fetch error:', err); setAffiliateLinks([]); });
  }, [categoryId, categoryMeta, settings.region]);

  // Auto-rotate spotlight carousel
  useEffect(() => {
    if (!data || data.spotlightSlides.length <= 1) return;

    const interval = setInterval(() => {
      setSpotlightIndex((prev) => {
        const next = (prev + 1) % data.spotlightSlides.length;
        spotlightRef.current?.scrollToIndex({ index: next, animated: true });
        return next;
      });
    }, 4000);

    return () => clearInterval(interval);
  }, [data]);

  // Discovery-mode: tap opens best affiliate URL directly; long-press opens picker sheet
  const [longPressItem, setLongPressItem] = useState<Item | null>(null);
  const [longPressSheetVisible, setLongPressSheetVisible] = useState(false);

  const handleItemPress = useCallback((item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = buildItemAffiliateUrl(item.name, affiliateLinks);
    openAffiliateUrl(url);
  }, [settings.hapticsEnabled, affiliateLinks]);

  const handleItemLongPress = useCallback((item: Item) => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setLongPressItem(item);
    setLongPressSheetVisible(true);
  }, [settings.hapticsEnabled]);

  const handleItemShopPress = useCallback((item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = buildItemAffiliateUrl(item.name, affiliateLinks);
    openAffiliateUrl(url);
  }, [settings.hapticsEnabled, affiliateLinks]);

  const handleEventPress = useCallback((eventId: string) => {
    router.push(`/events/${encodeURIComponent(eventId)}`);
  }, [router]);

  const handleFriendPress = useCallback((userId: string) => {
    router.push(`/users/${encodeURIComponent(userId)}`);
  }, [router]);

  const handleToggleFollow = useCallback(async () => {
    const newFollowing = !following;
    setFollowing(newFollowing);

    try {
      if (newFollowing) {
        await dataProvider.followCategory(categoryId!);
      } else {
        await dataProvider.unfollowCategory(categoryId!);
      }
    } catch (err) {
      // Revert on error
      setFollowing(!newFollowing);
      logger.warn('[Category] Follow toggle failed', err);
      showToast({ message: 'Could not update follow status. Please try again.', type: 'error' });
    }
  }, [following, categoryId, showToast]);

  const handleMarkOwned = useCallback(async (itemId: string) => {
    setMarkingOwned(itemId);
    try {
      await dataProvider.markCategoryItemOwned(itemId);

      // Fire success haptic
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

      // Mark as recently owned for visual feedback
      setRecentlyOwned((prev) => new Set(prev).add(itemId));

      // Remove from missing items list after brief delay for animation
      setTimeout(() => {
        setMissingItems((prev) => prev.filter((item) => item.id !== itemId));
        setRecentlyOwned((prev) => {
          const next = new Set(prev);
          next.delete(itemId);
          return next;
        });
      }, 600);
    } catch (err: unknown) {
      logger.warn('[CategoryStore] markOwned error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    } finally {
      setMarkingOwned(null);
    }
  }, [settings.hapticsEnabled]);

  const handleMissingShopItem = useCallback((title: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = buildItemAffiliateUrl(title, affiliateLinks);
    openAffiliateUrl(url);
  }, [settings.hapticsEnabled, affiliateLinks]);

  const handleMissingSeeMore = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({ pathname: '/category-browse', params: { categoryId: String(categoryId) } });
  }, [settings.hapticsEnabled, router, categoryId]);

  const handleMarketplaceHaptic = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [settings.hapticsEnabled]);

  const handleRelatedCategoryPress = useCallback((id: string) => {
    router.push(`/categories/${encodeURIComponent(id)}`);
  }, [router]);

  const handleSeeAllItems = useCallback(() => {
    showToast({ message: 'Browse external marketplaces below for more items', type: 'info' });
  }, [showToast]);

  const handleBuildProjectPress = useCallback((projectId: string) => {
    router.push(`/projects/${encodeURIComponent(projectId)}`);
  }, [router]);

  const handleBuildSeeAll = useCallback(() => {
    router.push('/build-paint-projects');
  }, [router]);

  const handleBuildStartNew = useCallback(() => {
    router.push('/build-paint-projects');
  }, [router]);

  // M10: Memoize props for heavy child components to prevent unnecessary re-renders
  // (must be before early returns to keep hook order stable)
  const missingItemsProps = useMemo(() => ({
    missingItems,
    recentlyOwned,
    markingOwned,
    accentColor,
    onMarkOwned: handleMarkOwned,
    onShopItem: handleMissingShopItem,
    onSeeMore: handleMissingSeeMore,
    colors,
  }), [missingItems, recentlyOwned, markingOwned, accentColor, handleMarkOwned, handleMissingShopItem, handleMissingSeeMore, colors]);

  const buildProjectsProps = useMemo(() => ({
    isBuildable,
    buildProjects,
    buildProjectsLoading,
    accentColor,
    onProjectPress: handleBuildProjectPress,
    onSeeAll: handleBuildSeeAll,
    onStartNew: handleBuildStartNew,
    colors,
  }), [isBuildable, buildProjects, buildProjectsLoading, accentColor, handleBuildProjectPress, handleBuildSeeAll, handleBuildStartNew, colors]);

  const categoryItemsProps = useMemo(() => ({
    items: data?.items ?? [],
    categoryName: data?.categoryName ?? '',
    accentColor,
    onItemPress: handleItemPress,
    onItemLongPress: handleItemLongPress,
    onShopPress: handleItemShopPress,
    onSeeAll: handleSeeAllItems,
    colors,
  }), [data?.items, data?.categoryName, accentColor, handleItemPress, handleItemLongPress, handleItemShopPress, handleSeeAllItems, colors]);

  const externalMarketplacesProps = useMemo(() => ({
    marketplaces: categoryMeta?.externalMarketplaces ?? [],
    affiliateLinks,
    onPress: handleMarketplaceHaptic,
    colors,
  }), [categoryMeta?.externalMarketplaces, affiliateLinks, handleMarketplaceHaptic, colors]);

  // Loading state
  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <SkeletonList count={4} type="card" />
        </View>
      </View>
    );
  }

  // Error / not found state
  if (error || !data) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>Category not found</Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This category doesn't exist or couldn't be loaded.
          </Text>
          <AnimatedPressable style={[styles.backButton, { borderColor: colors.border }]} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={[styles.backButtonText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.contentContainer}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        {/* 1. Category Header Card */}
        <CategoryHeaderCard
          categoryName={data.categoryName}
          categoryTagline={data.categoryTagline}
          following={following}
          onToggleFollow={handleToggleFollow}
          colors={colors}
        />

        {/* 1.5. Category Tips (first-time visitors) */}
        {categoryId && <CategoryTipsSection categoryId={categoryId} />}

        {/* 1.7. Grading Standards */}
        {categoryId && <CategoryGradingGuide categoryId={categoryId} />}

        {/* 2. Spotlight Carousel */}
        <SpotlightCarousel
          slides={data.spotlightSlides}
          spotlightIndex={spotlightIndex}
          spotlightRef={spotlightRef}
          onScrollEnd={setSpotlightIndex}
          colors={colors}
        />

        {/* 2.5. New Releases */}
        {categoryId && (
          <NewReleasesSection
            categoryId={categoryId}
            onItemPress={(item) => router.push({
              pathname: '/add-manual',
              params: { name: item.title, category: categoryId },
            })}
          />
        )}

        {/* 3. Items in this Category */}
        <CategoryItemsList
          {...categoryItemsProps}
        />

        {/* 3.15. Manga Series Progress */}
        <MangaSeriesProgress
          categoryId={categoryId}
          items={data.items}
          accentColor={accentColor}
          colors={colors}
        />

        {/* 3.25. Browse Catalog */}
        <CatalogBrowseSection
          catalogExpanded={catalogExpanded}
          onToggleExpanded={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            setCatalogExpanded(!catalogExpanded);
          }}
          catalogTotal={catalogTotal}
          catalogSearch={catalogSearch}
          onSearchChange={handleCatalogSearchChange}
          onClearSearch={() => {
            setCatalogSearch('');
            setCatalogOffset(0);
            loadCatalogItems('', 0, false);
          }}
          catalogLoading={catalogLoading}
          catalogLoadingMore={catalogLoadingMore}
          catalogItems={catalogItems}
          onLoadMore={handleCatalogLoadMore}
          onAddToCollection={(cItem) => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push({
              pathname: '/add-manual',
              params: {
                name: cItem.title,
                category: categoryId,
                // R50k: no catalog reference image forwarded to add-manual
              },
            });
          }}
          onAddToWatchlist={async (cItem) => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            try {
              await collectorsApi.addToWatchlist({
                title: cItem.title,
                category: categoryId || cItem.category,
                target_price: cItem.estimated_price,
              });
              showToast({ message: `${cItem.title} added to watchlist`, type: 'success' });
            } catch {
              showToast({ message: "Couldn't add to watchlist — try again", type: 'error' });
            }
          }}
          accentColor={accentColor}
          colors={colors}
        />

        {/* 3.5. Market Insights (Deep Dive) */}
        <MarketInsightsSection
          deepDive={deepDive}
          deepDiveLoading={deepDiveLoading}
          colors={colors}
        />

        {/* 4. Upcoming Events & Drops */}
        <CategoryEventsSection
          events={data.upcomingEvents}
          onEventPress={handleEventPress}
          colors={colors}
        />

        {/* 4.5. Set Completion Progress */}
        {categoryId && (
          <SetProgressSection
            categoryId={categoryId}
            onSetPress={(setId) => router.push(`/categories/${categoryId}` as Href)}
          />
        )}

        {/* 4.55. Featured Collections */}
        {categoryMeta && categoryId && (
          <FeaturedCollectionsSection
            collections={categoryMeta.collections}
            categoryId={categoryId}
            onCollectionPress={(name) => router.push({ pathname: '/(tabs)/items', params: { collection: name } })}
          />
        )}

        {/* 4.6. Missing Items Checklist */}
        <MissingItemsChecklist
          {...missingItemsProps}
        />

        {/* 4.6. Build Projects (hidden in beta) */}
        {!BETA_MODE && (
          <BuildProjectsSection
            {...buildProjectsProps}
          />
        )}

        {/* 5. Friends Who Follow */}
        <FriendsFollowSection
          friends={data.friendsWhoFollow}
          onFriendPress={handleFriendPress}
          colors={colors}
        />

        {/* 5.5. Category Leaderboard (hidden in beta) */}
        {!BETA_MODE && categoryId && <CategoryLeaderboardSection categoryId={categoryId} />}

        {/* 6. External Marketplace Links */}
        {categoryMeta && (
          <ExternalMarketplacesSection
            {...externalMarketplacesProps}
          />
        )}

        {/* 6.5. Cross-Category Correlation */}
        {categoryId && (
          <CrossCategorySection
            categoryId={categoryId}
            onCategoryPress={(catId) => router.push(`/categories/${catId}`)}
          />
        )}

        {/* 7. Related Categories */}
        <RelatedCategoriesSection
          categories={relatedCategories}
          onCategoryPress={handleRelatedCategoryPress}
          colors={colors}
        />

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>

      {/* Marketplace picker sheet for missing item "Find" button */}
      <MarketplacePickerSheet
        visible={shopSheetVisible}
        onClose={() => { setShopSheetVisible(false); setShopMissingItem(null); }}
        itemTitle={shopMissingItem?.title ?? ''}
        categoryId={categoryId}
      />

      {/* Marketplace picker sheet for catalog item long-press */}
      <MarketplacePickerSheet
        visible={longPressSheetVisible}
        onClose={() => { setLongPressSheetVisible(false); setLongPressItem(null); }}
        itemTitle={longPressItem?.name ?? ''}
        categoryId={categoryId}
      />

      <QuickNavBar />
    </View>
  );
}

export default function CategoryStoreScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Category Store">
      <CategoryStoreScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  container: {
    flex: 1,
  },
  contentContainer: {
    paddingHorizontal: 16,
    paddingTop: 0,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  errorTitle: {
    marginTop: 12,
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  errorSubtitle: {
    marginTop: 4,
    fontSize: text.md,
    textAlign: 'center',
  },
  backButton: {
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  backButtonText: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
  },
});
