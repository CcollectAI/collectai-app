/**
 * Category Store — Amazon Brand Store style layout for a category.
 * Shows: header, spotlight carousel, items, events, friends, sponsored slot.
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
  FlatList,
  Image,
  Linking,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategoryStoreData, type Item, type MiniUserProfile, type CategoryMissingItem, type BuildPaintProject } from '@/data';
import { getCategoryById, getRelatedCategories } from '@/data/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { isBuildableCategory } from '@/constants/buildStepTemplates';
import { CATEGORY_VISUAL } from '@/data/categories';
import logger from '@/utils/logger';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { SkeletonList } from '@/components/Skeleton';
import MarketplacePickerSheet from '@/components/MarketplacePickerSheet';
import { collectorsApi } from '@/api/collectorsApi';
import { buildItemAffiliateUrl, openAffiliateUrl } from '@/utils/affiliateHelpers';
import { QuickNavBar } from '@/components/QuickNavBar';
import { CatalogBrowseSection, type CatalogItemData } from '@/components/CatalogBrowseSection';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const kindIcon: Record<string, keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
};

const kindLabel: Record<string, string> = {
  collection_drop: 'Drop',
  meetup: 'Meetup',
  stream: 'Stream',
};

// Avatar component for friends
const FriendAvatar: React.FC<{ profile: MiniUserProfile; onPress: () => void; accentColor: string; textColor: string }> = ({
  profile,
  onPress,
  accentColor,
  textColor,
}) => {
  const initials = profile.displayName
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <AnimatedPressable style={styles.friendCard} onPress={onPress} accessibilityRole="button" accessibilityLabel={`View ${profile.displayName}'s profile`}>
      {profile.avatarUrl ? (
        <Image source={{ uri: profile.avatarUrl }} style={styles.friendAvatar} accessibilityLabel={`${profile.displayName} avatar`} />
      ) : (
        <View
          style={[
            styles.friendAvatar,
            styles.friendAvatarPlaceholder,
            { backgroundColor: profile.avatarColor || accentColor },
          ]}
        >
          <Text style={styles.friendInitials}>{initials}</Text>
        </View>
      )}
      <Text style={[styles.friendName, { color: textColor }]} numberOfLines={1}>
        {profile.displayName}
      </Text>
    </AnimatedPressable>
  );
};

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
  const [affiliateLinks, setAffiliateLinks] = useState<Array<{ source: string; url: string; affiliate_url: string; label: string }>>([]);

  // Market insights state
  const [deepDive, setDeepDive] = useState<Record<string, unknown> | null>(null);
  const [deepDiveLoading, setDeepDiveLoading] = useState(false);

  // Build projects state (for buildable categories)
  const [buildProjects, setBuildProjects] = useState<BuildPaintProject[]>([]);
  const [buildProjectsLoading, setBuildProjectsLoading] = useState(false);
  const isBuildable = categoryId ? isBuildableCategory(categoryId) : false;
  const accentColor = categoryId ? (CATEGORY_VISUAL[categoryId]?.accentColor ?? colors.accent) : colors.accent;

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
        .catch(() => setDeepDive(null));

      if (isBuildable) {
        dataProvider.listBuildPaintProjectsByCategory(categoryId)
          .then(setBuildProjects)
          .catch(() => setBuildProjects([]));
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
      .catch(() => {}); // Non-critical
  }, [categoryId]);

  // Load build projects for buildable categories
  useEffect(() => {
    if (!categoryId || !isBuildable) return;
    setBuildProjectsLoading(true);
    dataProvider.listBuildPaintProjectsByCategory(categoryId)
      .then(setBuildProjects)
      .catch((err) => {
        logger.warn('[CategoryStore] build projects fetch failed:', err);
        setBuildProjects([]);
      })
      .finally(() => setBuildProjectsLoading(false));
  }, [categoryId, isBuildable]);

  // Load market insights (deep dive)
  useEffect(() => {
    if (!categoryId) return;
    setDeepDiveLoading(true);
    dataProvider.getCategoryDeepDive(categoryId)
      .then(setDeepDive)
      .catch((err) => {
        logger.warn('[CategoryStore] deep dive fetch failed:', err);
        setDeepDive(null);
      })
      .finally(() => setDeepDiveLoading(false));
  }, [categoryId]);

  // Pre-fetch affiliate links for external marketplace section
  useEffect(() => {
    if (!categoryId || !categoryMeta) return;
    collectorsApi
      .getAffiliateLinks(categoryMeta.name, categoryId, 6, settings.region)
      .then((res) => setAffiliateLinks(res.links ?? []))
      .catch(() => setAffiliateLinks([]));
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

  const handleItemPress = (item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = buildItemAffiliateUrl(item.name, affiliateLinks);
    openAffiliateUrl(url);
  };

  const handleItemLongPress = (item: Item) => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setLongPressItem(item);
    setLongPressSheetVisible(true);
  };

  const handleEventPress = (eventId: string) => {
    router.push(`/events/${encodeURIComponent(eventId)}`);
  };

  const handleFriendPress = (userId: string) => {
    router.push(`/users/${encodeURIComponent(userId)}`);
  };

  const handleToggleFollow = async () => {
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
  };

  const handleMarkOwned = async (itemId: string) => {
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
  };

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
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#81D8D0" />}
      >
        {/* 1. Category Header Card */}
        <View style={[styles.headerCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.headerContent}>
            <Text style={[styles.categoryName, { color: colors.text }]}>{data.categoryName}</Text>
            <Text style={[styles.categoryTagline, { color: colors.muted }]} numberOfLines={3}>
              {data.categoryTagline}
            </Text>
          </View>
          <AnimatedPressable
            style={[
              styles.followButton,
              { borderColor: colors.accent },
              following && { backgroundColor: colors.accent },
            ]}
            onPress={handleToggleFollow}
            accessibilityRole="button"
            accessibilityLabel={following ? `Unfollow ${data.categoryName}` : `Follow ${data.categoryName}`}
          >
            <Ionicons
              name={following ? 'checkmark' : 'add'}
              size={16}
              color={following ? '#fff' : colors.accent}
            />
            <Text
              style={[
                styles.followButtonText,
                { color: colors.accent },
                following && { color: '#fff' },
              ]}
            >
              {following ? 'Following' : 'Follow'}
            </Text>
          </AnimatedPressable>
        </View>

      {/* 2. Spotlight Carousel */}
      {data.spotlightSlides.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Spotlight</Text>
          <FlatList
            ref={spotlightRef}
            data={data.spotlightSlides}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            keyExtractor={(slide) => slide.id}
            onMomentumScrollEnd={(e) => {
              const index = Math.round(e.nativeEvent.contentOffset.x / (SCREEN_WIDTH - 32));
              setSpotlightIndex(index);
            }}
            renderItem={({ item: slide }) => (
              <View style={[styles.spotlightSlide, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {slide.imageUrl ? (
                  <View style={styles.spotlightImageWrap}>
                    <Image source={{ uri: slide.imageUrl }} style={styles.spotlightImage} />
                    <View style={styles.spotlightImageOverlay} />
                  </View>
                ) : (
                  <View style={[styles.spotlightImagePlaceholder, { backgroundColor: colors.background }]}>
                    <Ionicons name="sparkles" size={32} color={colors.accent} />
                  </View>
                )}
                <Text style={[styles.spotlightTitle, { color: colors.text }]}>{slide.title}</Text>
                {slide.subtitle && (
                  <Text style={[styles.spotlightSubtitle, { color: colors.muted }]}>{slide.subtitle}</Text>
                )}
              </View>
            )}
          />
          {/* Dots indicator */}
          {data.spotlightSlides.length > 1 && (
            <View style={styles.dotsRow}>
              {data.spotlightSlides.map((_, idx) => (
                <View
                  key={idx}
                  style={[
                    styles.dot,
                    { backgroundColor: colors.border },
                    idx === spotlightIndex && { backgroundColor: colors.accent },
                  ]}
                />
              ))}
            </View>
          )}
        </View>
      )}

      {/* 3. Items in this Category */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Items in {data.categoryName}</Text>
        {data.items.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>No items yet in this category.</Text>
        ) : (
          data.items.slice(0, 6).map((item) => (
            <AnimatedPressable
              key={item.id}
              style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => handleItemPress(item)}
              onLongPress={() => handleItemLongPress(item)}
              accessibilityRole="button"
              accessibilityLabel={`Shop for ${item.name}, ${formatPrice(item.price)}. Long press for more marketplaces.`}
            >
              {item.imageUrl ? (
                <Image source={{ uri: item.imageUrl }} style={styles.itemThumb} />
              ) : (
                <View style={[styles.itemThumbPlaceholder, { backgroundColor: '#81D8D0' + '10' }]}>
                  <Ionicons name="cube-outline" size={18} color="#81D8D0" />
                </View>
              )}
              <View style={styles.itemInfo}>
                <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={[styles.itemCategory, { color: colors.muted }]}>
                  {formatPrice(item.price)}
                </Text>
              </View>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  const url = buildItemAffiliateUrl(item.name, affiliateLinks);
                  openAffiliateUrl(url);
                }}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={`Shop for ${item.name} on marketplaces`}
              >
                <Ionicons name="open-outline" size={20} color="#81D8D0" />
              </AnimatedPressable>
            </AnimatedPressable>
          ))
        )}
        {data.items.length > 6 && (
          <AnimatedPressable
            style={styles.seeAllButton}
            onPress={() => {
              showToast({ message: 'Browse external marketplaces below for more items', type: 'info' });
            }}
            accessibilityRole="link"
            accessibilityLabel={`See all ${data.items.length} items in catalog`}
          >
            <Text style={[styles.seeAllText, { color: accentColor }]}>
              See all {data.items.length} items
            </Text>
            <Ionicons name="arrow-forward" size={14} color={accentColor} />
          </AnimatedPressable>
        )}
      </View>

      {/* 3.15. Manga Series Progress — shows per-series volume counts */}
      {categoryId === 'manga' && data.items.length > 0 && (() => {
        // Group items by series title (from attributes or name prefix)
        const seriesMap: Record<string, { count: number; total?: number; items: typeof data.items }> = {};
        for (const item of data.items) {
          // Try to extract series name from attributes or item name
          const attrs = (item as Record<string, unknown>).attributesJson as Record<string, unknown> | undefined;
          const seriesName = (attrs?.title as string) || item.name.replace(/\s*vol\.?\s*\d+.*/i, '').replace(/\s*#\d+.*/i, '').trim();
          if (!seriesName) continue;
          if (!seriesMap[seriesName]) {
            seriesMap[seriesName] = { count: 0, total: undefined, items: [] };
          }
          seriesMap[seriesName].count += 1;
          seriesMap[seriesName].items.push(item);
          // Try to get total_volumes from attributes
          const totalVols = attrs?.total_volumes;
          if (totalVols && typeof totalVols === 'string' && parseInt(totalVols, 10) > 0) {
            seriesMap[seriesName].total = parseInt(totalVols, 10);
          }
        }

        const seriesEntries = Object.entries(seriesMap)
          .filter(([_, s]) => s.count > 0)
          .sort((a, b) => b[1].count - a[1].count);

        if (seriesEntries.length === 0) return null;

        return (
          <View style={styles.section}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Ionicons name="library-outline" size={18} color={accentColor} />
              <Text style={[styles.sectionTitle, { color: colors.text, marginBottom: 0 }]}>Series Progress</Text>
            </View>
            {seriesEntries.slice(0, 8).map(([seriesName, series]) => {
              const pct = series.total ? Math.min(100, Math.round((series.count / series.total) * 100)) : null;
              return (
                <View key={seriesName} style={[styles.seriesProgressCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                  <View style={styles.seriesProgressHeader}>
                    <Text style={[styles.seriesProgressName, { color: colors.text }]} numberOfLines={1}>
                      {seriesName}
                    </Text>
                    <Text style={[styles.seriesProgressCount, { color: accentColor }]}>
                      {series.count}{series.total ? `/${series.total}` : ''} vol
                    </Text>
                  </View>
                  {pct !== null && (
                    <View style={[styles.seriesProgressBarBg, { backgroundColor: colors.border }]}>
                      <View
                        style={[
                          styles.seriesProgressBarFill,
                          { backgroundColor: pct >= 100 ? '#22C55E' : accentColor, width: `${pct}%` },
                        ]}
                      />
                    </View>
                  )}
                  {pct !== null && pct >= 100 && (
                    <View style={[styles.seriesCompleteBadge, { backgroundColor: '#D1FAE5' }]}>
                      <Ionicons name="checkmark-circle" size={14} color="#065F46" />
                      <Text style={{ fontSize: 11, fontWeight: '600', color: '#065F46' }}>Complete!</Text>
                    </View>
                  )}
                </View>
              );
            })}
            {seriesEntries.length > 8 && (
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                +{seriesEntries.length - 8} more series
              </Text>
            )}
          </View>
        );
      })()}

      {/* 3.25. Browse Catalog — full category_items database browser */}
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
              imageUri: cItem.image_url || '',
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
            showToast({ message: `${cItem.title} added to want list`, type: 'success' });
          } catch {
            showToast({ message: 'Failed to add to want list', type: 'error' });
          }
        }}
        accentColor={accentColor}
        colors={colors}
      />

      {/* 3.5. Market Insights (Deep Dive) */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Market Insights</Text>
        {deepDiveLoading ? (
          <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
        ) : deepDive ? (
          <>
            {/* Average Market Price */}
            {typeof deepDive.average_market_price === 'number' && deepDive.average_market_price > 0 && (
              <View style={[styles.insightCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.insightLabel, { color: colors.muted }]}>Average Market Price</Text>
                <Text style={[styles.insightValue, { color: colors.text }]}>
                  {formatPrice(deepDive.average_market_price as number)}
                </Text>
              </View>
            )}

            {/* Price Trend */}
            {deepDive.value_distribution && typeof deepDive.value_distribution === 'object' && (
              <View style={[styles.insightCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.insightLabel, { color: colors.muted }]}>Price Trend</Text>
                <View style={styles.trendRow}>
                  <Ionicons
                    name={
                      (deepDive.value_distribution as Record<string, unknown>).trend === 'up'
                        ? 'trending-up'
                        : (deepDive.value_distribution as Record<string, unknown>).trend === 'down'
                        ? 'trending-down'
                        : 'remove-outline'
                    }
                    size={18}
                    color={
                      (deepDive.value_distribution as Record<string, unknown>).trend === 'up'
                        ? '#10B981'
                        : (deepDive.value_distribution as Record<string, unknown>).trend === 'down'
                        ? '#EF4444'
                        : colors.muted
                    }
                  />
                  <Text style={[styles.trendText, {
                    color: (deepDive.value_distribution as Record<string, unknown>).trend === 'up'
                      ? '#10B981'
                      : (deepDive.value_distribution as Record<string, unknown>).trend === 'down'
                      ? '#EF4444'
                      : colors.muted,
                  }]}>
                    {(deepDive.value_distribution as Record<string, unknown>).trend === 'up'
                      ? 'Prices trending up'
                      : (deepDive.value_distribution as Record<string, unknown>).trend === 'down'
                      ? 'Prices trending down'
                      : 'Prices stable'}
                  </Text>
                </View>
              </View>
            )}

            {/* Top Traded Items */}
            {Array.isArray(deepDive.top_traded_items) && (deepDive.top_traded_items as Array<Record<string, unknown>>).length > 0 && (
              <View style={styles.insightSubSection}>
                <Text style={[styles.insightSubTitle, { color: colors.text }]}>Top Traded Items</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.topTradedRow}>
                  {(deepDive.top_traded_items as Array<Record<string, unknown>>).map((item, idx) => (
                    <View
                      key={String(item.id ?? idx)}
                      style={[styles.topTradedCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                    >
                      <Text style={[styles.topTradedName, { color: colors.text }]} numberOfLines={2}>
                        {String(item.name ?? item.title ?? 'Unknown')}
                      </Text>
                      <Text style={[styles.topTradedCount, { color: colors.muted }]}>
                        {String(item.trade_count ?? item.tradeCount ?? 0)} trades
                      </Text>
                    </View>
                  ))}
                </ScrollView>
              </View>
            )}

            {/* Top Movers */}
            {Array.isArray(deepDive.top_movers) && (deepDive.top_movers as Array<Record<string, unknown>>).length > 0 && (
              <View style={styles.insightSubSection}>
                <Text style={[styles.insightSubTitle, { color: colors.text }]}>Top Movers</Text>
                {(deepDive.top_movers as Array<Record<string, unknown>>).map((mover, idx) => {
                  const changePct = Number(mover.change_pct ?? mover.changePct ?? 0);
                  const isPositive = changePct >= 0;
                  return (
                    <View
                      key={String(mover.id ?? idx)}
                      style={[styles.moverRow, { borderBottomColor: colors.border }]}
                    >
                      <Text style={[styles.moverName, { color: colors.text }]} numberOfLines={1}>
                        {String(mover.name ?? mover.title ?? 'Unknown')}
                      </Text>
                      <Text style={[styles.moverPct, { color: isPositive ? '#10B981' : '#EF4444' }]}>
                        {isPositive ? '+' : ''}{changePct.toFixed(1)}%
                      </Text>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        ) : (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            No market insights available for this category yet.
          </Text>
        )}
      </View>

      {/* 4. Upcoming Events / Drops */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Upcoming Events & Drops</Text>
        {data.upcomingEvents.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>No upcoming events for this category.</Text>
        ) : (
          data.upcomingEvents.map((event) => (
            <AnimatedPressable
              key={event.id}
              style={[styles.eventCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => handleEventPress(event.id)}
              accessibilityRole="button"
              accessibilityLabel={`${event.title}, ${kindLabel[event.kind] || event.kind}, ${event.date}`}
            >
              <View
                style={[
                  styles.eventIconBubble,
                  { backgroundColor: colors.accent },
                ]}
              >
                <Ionicons
                  name={kindIcon[event.kind] || 'calendar-outline'}
                  size={18}
                  color="#fff"
                />
              </View>
              <View style={styles.eventInfo}>
                <Text style={[styles.eventTitle, { color: colors.text }]} numberOfLines={1}>
                  {event.title}
                </Text>
                <Text style={[styles.eventMeta, { color: colors.muted }]}>
                  {kindLabel[event.kind] || event.kind} · {event.date}
                  {event.time ? ` · ${event.time}` : ''}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </AnimatedPressable>
          ))
        )}
      </View>

      {/* 4.5. Missing Items Checklist - above Friends */}
      {missingItems.length > 0 && (
        <View style={[styles.missingCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.missingCardHeader}>
            <Text style={[styles.missingCardTitle, { color: colors.text }]}>
              Complete Your Collection
            </Text>
            <Text style={[styles.missingCardCount, { color: colors.muted }]}>
              {missingItems.length} left
            </Text>
          </View>
          {missingItems.slice(0, 3).map((item) => {
            const isOwned = recentlyOwned.has(item.id);
            const isMarking = markingOwned === item.id;

            return (
              <View
                key={item.id}
                style={[
                  styles.missingChecklistRow,
                  { borderBottomColor: colors.border },
                ]}
              >
                <View
                  style={[
                    styles.missingCheckbox,
                    { borderColor: isOwned ? colors.accent : colors.border },
                    isOwned && { backgroundColor: colors.accent },
                  ]}
                >
                  {isOwned && <Ionicons name="checkmark" size={12} color="#fff" />}
                </View>
                <View style={styles.missingInfo}>
                  <Text
                    style={[
                      styles.missingTitle,
                      { color: isOwned ? colors.muted : colors.text },
                      isOwned && styles.missingTitleOwned,
                    ]}
                    numberOfLines={1}
                  >
                    {item.title}
                  </Text>
                  {item.brand && (
                    <Text style={[styles.missingBrand, { color: colors.muted }]} numberOfLines={1}>
                      {item.brand}
                    </Text>
                  )}
                </View>
                {!isOwned && (
                  <AnimatedPressable
                    style={[styles.missingFindBtn, { borderColor: accentColor }]}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      const url = buildItemAffiliateUrl(item.title, affiliateLinks);
                      openAffiliateUrl(url);
                    }}
                    accessibilityRole="button"
                    accessibilityLabel={`Shop for ${item.title} on marketplaces`}
                  >
                    <Ionicons name="open-outline" size={16} color={accentColor} />
                  </AnimatedPressable>
                )}
                <AnimatedPressable
                  style={[
                    styles.missingAddBtn,
                    {
                      backgroundColor: isOwned ? 'transparent' : colors.accent,
                    },
                  ]}
                  disabled={isMarking || isOwned}
                  onPress={() => handleMarkOwned(item.id)}
                  accessibilityRole="button"
                  accessibilityLabel={isOwned ? `${item.title} marked as owned` : `Add ${item.title}`}
                >
                  {isMarking ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : isOwned ? (
                    <Text style={[styles.missingAddBtnText, { color: colors.accent }]}>Added</Text>
                  ) : (
                    <Text style={styles.missingAddBtnText}>Add</Text>
                  )}
                </AnimatedPressable>
              </View>
            );
          })}
          {missingItems.length > 3 && (
            <AnimatedPressable
              style={styles.missingFooter}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/categories/');
              }}
              accessibilityRole="button"
              accessibilityLabel={`View ${missingItems.length - 3} more items to collect across categories`}
            >
              <Text style={[styles.seeMore, { color: colors.accent }]}>
                +{missingItems.length - 3} more to collect
              </Text>
              <Ionicons name="arrow-forward" size={14} color={colors.accent} />
            </AnimatedPressable>
          )}
        </View>
      )}

      {/* 4.6. Build Projects — for buildable categories */}
      {isBuildable && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Build & Paint Projects</Text>
            {buildProjects.length > 0 && (
              <Text style={[styles.sectionCount, { color: colors.muted }]}>
                {buildProjects.length} project{buildProjects.length !== 1 ? 's' : ''}
              </Text>
            )}
          </View>
          {buildProjectsLoading ? (
            <ActivityIndicator size="small" color={accentColor} style={{ marginVertical: 12 }} />
          ) : buildProjects.length > 0 ? (
            <>
              {buildProjects.slice(0, 3).map((project) => {
                const pct = project.percent ?? 0;

                return (
                  <AnimatedPressable
                    key={project.id}
                    style={[styles.buildProjectCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                    onPress={() => router.push(`/projects/${encodeURIComponent(project.id)}`)}
                    accessibilityRole="button"
                    accessibilityLabel={`${project.title}, ${pct}% complete`}
                  >
                    <View style={[styles.buildProjectAccent, { backgroundColor: accentColor }]} />
                    <View style={styles.buildProjectInfo}>
                      <Text style={[styles.buildProjectTitle, { color: colors.text }]} numberOfLines={1}>
                        {project.title}
                      </Text>
                      <View style={styles.buildProjectProgressRow}>
                        <View style={[styles.buildProjectProgressBg, { backgroundColor: colors.border }]}>
                          <View style={[styles.buildProjectProgressFill, { backgroundColor: accentColor, width: `${pct}%` }]} />
                        </View>
                        <Text style={[styles.buildProjectPct, { color: colors.muted }]}>{pct}%</Text>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </AnimatedPressable>
                );
              })}
              {buildProjects.length > 3 && (
                <AnimatedPressable
                  style={styles.seeAllButton}
                  onPress={() => router.push('/build-paint-projects')}
                  accessibilityRole="link"
                  accessibilityLabel={`See all ${buildProjects.length} build projects`}
                >
                  <Text style={[styles.seeAllText, { color: accentColor }]}>
                    See all {buildProjects.length} projects
                  </Text>
                  <Ionicons name="arrow-forward" size={14} color={accentColor} />
                </AnimatedPressable>
              )}
            </>
          ) : (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No build projects in this category yet.
            </Text>
          )}
          <AnimatedPressable
            style={[styles.startBuildBtn, { backgroundColor: accentColor }]}
            onPress={() => router.push('/build-paint-projects')}
            accessibilityRole="button"
            accessibilityLabel="Start a new build project"
          >
            <Ionicons name="construct-outline" size={16} color="#fff" />
            <Text style={styles.startBuildBtnText}>Start New Build</Text>
          </AnimatedPressable>
        </View>
      )}

      {/* 5. Friends Who Follow */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Friends Who Follow</Text>
        {data.friendsWhoFollow.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            None of your friends follow this category yet.
          </Text>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.friendsRow}
          >
            {data.friendsWhoFollow.map((friend) => (
              <FriendAvatar
                key={friend.id}
                profile={friend}
                onPress={() => handleFriendPress(friend.id)}
                accentColor={colors.accent}
                textColor={colors.text}
              />
            ))}
          </ScrollView>
        )}
      </View>

      {/* 6. External Marketplace Links (affiliate-tagged) */}
      {categoryMeta && categoryMeta.externalMarketplaces.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>External Marketplaces</Text>
          <View style={styles.marketplaceRow}>
            {categoryMeta.externalMarketplaces.map((mp) => {
              // Use pre-fetched affiliate URL if available, otherwise fall back to raw URL
              const affiliateMatch = affiliateLinks.find(
                (al) => al.source.toLowerCase() === mp.id.toLowerCase()
              );
              const url = affiliateMatch?.affiliate_url ?? mp.url;
              return (
                <AnimatedPressable
                  key={mp.id}
                  style={[styles.marketplaceBtn, { backgroundColor: '#81D8D0' + '15', borderColor: '#81D8D0' }]}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    Linking.openURL(url).catch((err) => logger.warn('[CategoryStore] open URL error:', err));
                  }}
                  accessibilityRole="link"
                  accessibilityLabel={`Shop ${mp.label}`}
                >
                  <Ionicons name="open-outline" size={14} color="#81D8D0" />
                  <Text style={[styles.marketplaceBtnText, { color: '#81D8D0' }]}>{mp.label}</Text>
                </AnimatedPressable>
              );
            })}
          </View>
        </View>
      )}

      {/* 7. Related Categories */}
      {relatedCategories.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Related Categories</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.relatedRow}>
            {relatedCategories.map((rc) => (
              <AnimatedPressable
                key={rc.id}
                style={[styles.relatedCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => router.push(`/categories/${encodeURIComponent(rc.id)}`)}
                accessibilityRole="button"
                accessibilityLabel={`Browse ${rc.name}`}
              >
                <Text style={[styles.relatedName, { color: colors.text }]} numberOfLines={2}>{rc.name}</Text>
                <Text style={[styles.relatedTagline, { color: colors.muted }]} numberOfLines={2}>{rc.tagline}</Text>
              </AnimatedPressable>
            ))}
          </ScrollView>
        </View>
      )}

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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingTop: 0,
    paddingBottom: 4,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  errorTitle: {
    marginTop: 12,
    fontSize: 16,
    fontWeight: '600',
  },
  errorSubtitle: {
    marginTop: 4,
    fontSize: 13,
    textAlign: 'center',
  },
  backButton: {
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
  },
  backButtonText: {
    fontSize: 13,
    fontWeight: '500',
  },

  // Header card
  headerCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  headerContent: {
    marginBottom: 12,
  },
  categoryName: {
    fontSize: 20,
    fontWeight: '700',
  },
  categoryTagline: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
  },
  followButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  followButtonText: {
    marginLeft: 4,
    fontSize: 13,
    fontWeight: '600',
  },

  // Sections
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  emptyText: {
    fontSize: 13,
  },

  // Missing items checklist card
  missingCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 20,
  },
  missingCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  missingCardTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  missingCardCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  missingChecklistRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  missingCheckbox: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  missingInfo: {
    flex: 1,
  },
  missingTitle: {
    fontSize: 14,
    fontWeight: '500',
  },
  missingTitleOwned: {
    textDecorationLine: 'line-through',
  },
  missingBrand: {
    fontSize: 12,
    marginTop: 2,
  },
  missingFindBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  missingAddBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
    marginLeft: 8,
  },
  missingAddBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  missingFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 10,
  },
  seeMore: {
    fontSize: 13,
    fontWeight: '500',
    textAlign: 'center',
  },

  // Spotlight carousel
  spotlightSlide: {
    width: SCREEN_WIDTH - 32,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    alignItems: 'center',
  },
  spotlightImageWrap: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 12,
  },
  spotlightImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  spotlightImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.15)',
  },
  spotlightImagePlaceholder: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  spotlightTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  spotlightSubtitle: {
    marginTop: 2,
    fontSize: 12,
    textAlign: 'center',
  },
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 10,
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },

  // Items
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginBottom: 8,
  },
  itemThumb: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
  },
  itemThumbPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemInfo: {
    flex: 1,
    marginRight: 8,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemCategory: {
    fontSize: 12,
    marginTop: 2,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '700',
    marginRight: 8,
  },
  seeAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    gap: 4,
  },
  seeAllText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Events
  eventCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    marginBottom: 8,
  },
  eventIconBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  eventInfo: {
    flex: 1,
    marginRight: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  eventMeta: {
    fontSize: 11,
    marginTop: 2,
  },

  // Friends
  friendsRow: {
    gap: 12,
  },
  friendCard: {
    alignItems: 'center',
    width: 64,
  },
  friendAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
  },
  friendAvatarPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  friendInitials: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  friendName: {
    marginTop: 4,
    fontSize: 11,
    textAlign: 'center',
  },

  // Sponsored
  sponsoredCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  sponsoredLabel: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  sponsoredPlaceholder: {
    height: 60,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  sponsoredText: {
    fontSize: 12,
  },

  // Market Insights
  insightCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 8,
  },
  insightLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  insightValue: {
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
  },
  trendText: {
    fontSize: 14,
    fontWeight: '600',
  },
  insightSubSection: {
    marginTop: 8,
  },
  insightSubTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  topTradedRow: {
    gap: 10,
  },
  topTradedCard: {
    width: 140,
    borderRadius: 10,
    borderWidth: 1,
    padding: 10,
  },
  topTradedName: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 4,
  },
  topTradedCount: {
    fontSize: 11,
  },
  moverRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  moverName: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
    marginRight: 8,
  },
  moverPct: {
    fontSize: 13,
    fontWeight: '700',
  },

  // External Marketplace Links
  marketplaceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  marketplaceBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  marketplaceBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Build project cards
  buildProjectCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 8,
  },
  buildProjectAccent: {
    width: 4,
    alignSelf: 'stretch',
  },
  buildProjectInfo: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  buildProjectTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
  },
  buildProjectProgressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  buildProjectProgressBg: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  buildProjectProgressFill: {
    height: '100%',
    borderRadius: 2,
  },
  buildProjectPct: {
    fontSize: 11,
    fontWeight: '600',
    minWidth: 28,
    textAlign: 'right',
  },
  startBuildBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    marginTop: 8,
  },
  startBuildBtnText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },

  // Related Categories
  relatedRow: {
    gap: 10,
  },
  relatedCard: {
    width: 160,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  relatedName: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
  },
  relatedTagline: {
    fontSize: 11,
    lineHeight: 15,
  },

  seriesProgressCard: {
    borderRadius: 10,
    borderWidth: 1,
    padding: 12,
    marginBottom: 8,
  },
  seriesProgressHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  seriesProgressName: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
    marginRight: 8,
  },
  seriesProgressCount: {
    fontSize: 13,
    fontWeight: '700',
  },
  seriesProgressBarBg: {
    height: 6,
    borderRadius: 3,
    marginTop: 8,
    overflow: 'hidden',
  },
  seriesProgressBarFill: {
    height: 6,
    borderRadius: 3,
  },
  seriesCompleteBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginTop: 6,
  },
});
