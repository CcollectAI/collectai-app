/**
 * Category Store — the "one carousel that earns" museum layout
 * (web/category-redesign-preview.html).
 *
 * Page order mirrors the mockup:
 *   1. Brand header (paid sponsor zone — stub, dark until a sponsor exists)
 *   2. Category header card (organic header + Follow + Invite/Find friends)
 *   3. Category overview rails (sort chips → main rail, then BY SET rail;
 *      every tap → museum detail → affiliate buy)
 *   4. (Market insights — REMOVED 2026-08-11; see below)
 *   — below the fold —
 *   5. Upcoming events (category-tagged first, then the events-tab pool)
 *   6. Related categories
 *
 * Everything else the old page stacked (Spotlight, Items-in-Category,
 * Featured Collections, Browse Catalog, Tips, Grading Guide, Missing Items,
 * Build Projects, External Marketplaces, Cross-Category, Leaderboard) is
 * deliberately GONE — merged into or funneled through the single rail.
 *
 * Perf: the page renders instantly from local category metadata
 * (getCategoryById is synchronous) — there is NO full-screen skeleton and no
 * blocking fetch. The rail and events each load their own data and stream in as
 * they arrive.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter, Stack, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategoryStoreData } from '@/data';
import { getCategoryById, getRelatedCategories } from '@/data/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { guideFor } from '@/data/collectingGuides';
import logger from '@/utils/logger';
import { logAuthState, logLoad, startTimer } from '@/utils/diagnostics';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { QuickNavBar } from '@/components/QuickNavBar';
import ScreenHeader from '@/components/ScreenHeader';
import { radius, text, fontWeight } from '@/theme/tokens';
import {
  CategoryHeaderCard,
  CategoryEventsSection,
  RelatedCategoriesSection,
  CategoryOverviewRail,
  CategoryBrandHeader,
  CategorySortChips,
  FeaturedCollectionsSection,
} from '@/components/category';
import type { CatalogSortKey } from '@/components/category/CategorySortChips';
import { safeGoBack } from '@/lib/goBack';

function CategoryStoreScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const router = useRouter();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { showToast } = useToast();

  // Category identity is LOCAL data — render the page shell immediately.
  const categoryMeta = categoryId ? getCategoryById(categoryId) : undefined;
  const relatedCategories = categoryMeta ? getRelatedCategories(categoryMeta) : [];
  // null for most categories, and that is the normal case — see
  // src/data/collectingGuides.ts. The banner below branches on it.
  const guide = guideFor(categoryId);
  const accentColor = colors.accent;

  const [following, setFollowing] = useState(false);
  const [events, setEvents] = useState<CategoryStoreData['upcomingEvents']>([]);

  // Catalog sort — owned here so CategorySortChips (mockup: page-level, under
  // the header) and the rail share it. Default 'value': commission is a % of
  // price, so the highest-earning items lead.
  const [catalogSort, setCatalogSort] = useState<CatalogSortKey>('value');


  const [refreshing, setRefreshing] = useState(false);

  // Events + friends (non-blocking; swr-cached in CachedDataProvider) and
  // the deep-dive insights stream in after first paint.
  const loadCategoryData = useCallback(async () => {
    if (!categoryId) return;

    const elapsed = startTimer();
    logAuthState(`category:${categoryId}`);
    try {
      const storeResult = await dataProvider.getCategoryStore(categoryId);
      if (storeResult) {
        setEvents(storeResult.upcomingEvents);
      }
      logLoad(`category:${categoryId}`, {
        events: storeResult?.upcomingEvents.length ?? 'null-store',
        items: storeResult?.items.length ?? 'null-store',
        ms: elapsed(),
      });
    } catch (err: unknown) {
      logLoad(`category:${categoryId}`, { error: err instanceof Error ? err.message : String(err), ms: elapsed() });
      logger.error('[CategoryStore] store fetch error:', err);
    }

    // The deep-dive fetch is GONE with the market-value card (2026-08-11).
    // It existed only to feed MarketInsightsSection; nothing else read it, so
    // keeping the call would be a request whose response goes nowhere.
  }, [categoryId]);

  useEffect(() => {
    loadCategoryData();
  }, [loadCategoryData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadCategoryData();
    setRefreshing(false);
  }, [loadCategoryData]);

  // Load follow state
  useEffect(() => {
    if (!categoryId) return;
    dataProvider.isFollowingCategory(categoryId)
      .then((isFollowing) => {
        setFollowing(isFollowing);
        logLoad(`follow:${categoryId}`, { following: isFollowing });
      })
      .catch((err) => {
        logLoad(`follow:${categoryId}`, { error: err instanceof Error ? err.message : String(err) });
        logger.info('[Category] follow state fetch error:', err);
      });
  }, [categoryId]);

  const handleEventPress = useCallback((eventId: string) => {
    router.push(`/events/${encodeURIComponent(eventId)}`);
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
      logger.error('[Category] Follow toggle failed', err);
      // Surface the real failure (status + detail) — a generic message hides
      // whether this is auth, network, or a server error.
      const detail = err instanceof Error && err.message ? ` (${err.message})` : '';
      showToast({ message: `Could not update follow status. Please try again.${detail}`, type: 'error' });
    }
  }, [following, categoryId, showToast]);

  const handleRelatedCategoryPress = useCallback((id: string) => {
    router.push(`/categories/${encodeURIComponent(id)}`);
  }, [router]);

  // Not found — the only state that blocks the page (identity is local data).
  if (!categoryId || !categoryMeta) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>Category not found</Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This category doesn&apos;t exist or couldn&apos;t be loaded.
          </Text>
          <AnimatedPressable style={[styles.backButton, { borderColor: colors.border }]} onPress={() => safeGoBack(router)} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={[styles.backButtonText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      {/* Native header off — flat ScreenHeader instead (no iOS 26 glass on the
          back/chat/settings icons). Title-less: the teal banner below already
          names the category. */}
      <Stack.Screen options={{ headerShown: false }} />
      <ScreenHeader />
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.contentContainer}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        {/* 1. Brand header — lit up only when a brand sponsors the category
            (stub today; a category_sponsors record drives it later). */}
        <CategoryBrandHeader sponsor={null} colors={colors} />

        {/* 2. Organic category header + Follow */}
        <CategoryHeaderCard
          categoryName={categoryMeta.name}
          categoryTagline={categoryMeta.tagline}
          following={following}
          onToggleFollow={handleToggleFollow}
          colors={colors}
        />

        {/* 2b. "New to this?" — ONLY where a guide exists. Most of the 56
            categories have none, and a banner promising a guide that opens an
            empty page is the dead-end this codebase keeps paying for. It sits
            above the catalogue because someone who does not know what a holo is
            cannot use a sort control yet. */}
        {guide ? (
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push({
                pathname: '/guide/[categoryId]',
                params: { categoryId },
              } as unknown as Href);
            }}
            style={[styles.guideBanner, { backgroundColor: colors.accent + '14', borderColor: colors.accent + '40' }]}
            accessibilityRole="button"
            accessibilityLabel={`How to start collecting ${categoryMeta.name}`}
          >
            <View style={[styles.guideIcon, { backgroundColor: colors.accent + '22' }]}>
              <Ionicons name="school-outline" size={20} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.guideTitle, { color: colors.text }]}>
                New to {categoryMeta.name}?
              </Text>
              <Text style={[styles.guideSub, { color: colors.muted }]} numberOfLines={2}>
                The words, what to look after, what to avoid, and where to start.
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </AnimatedPressable>
        ) : null}

        {/* 2c. Sets you are close to finishing, scoped to THIS category.
            app/sets-to-complete.tsx has been a complete 14KB feature reachable
            from nowhere — registered as a route, pushed to by nothing, so a
            repo-wide search for a link returned zero hits. This is its entry
            point. It shows nothing useful until you own 2+ items from one set,
            which is why it lives below the guide rather than at the top. */}
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push({
              pathname: '/sets-to-complete',
              params: { categoryId },
            } as unknown as Href);
          }}
          style={[styles.setsRow, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`Sets you are close to completing in ${categoryMeta.name}`}
        >
          <View style={[styles.guideIcon, { backgroundColor: colors.success + '1E' }]}>
            <Ionicons name="albums-outline" size={20} color={colors.success} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.guideTitle, { color: colors.text }]}>Finish a set</Text>
            <Text style={[styles.guideSub, { color: colors.muted }]} numberOfLines={2}>
              What you are still missing from sets you have already started.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>

        {/* 3a. Page-level sort chips (mockup `.chips` — gradient active pill). */}
        <CategorySortChips
          sort={catalogSort}
          onChange={setCatalogSort}
          colors={colors}
        />

        {/* 3b. The category overview rail → museum → affiliate "Where to
            buy". A browsable gallery of what EXISTS in the category; every
            tap opens the catalog museum detail. */}
        <CategoryOverviewRail
          categoryId={categoryId}
          categoryName={categoryMeta.name}
          sort={catalogSort}
          accentColor={accentColor}
          colors={colors}
          onSeeAll={() => router.push({
            pathname: '/category-browse',
            params: { categoryId: String(categoryId) },
          } as unknown as Href)}
          onItemPress={(it) => router.push({
            pathname: '/catalog-item/[key]',
            params: {
              key: it.item_key, category: it.category, title: it.title,
              image_url: it.image_url ?? '', rarity: it.rarity ?? '',
              set_code: it.set_code ?? '', brand: it.brand ?? '',
              estimated_price: it.estimated_price != null ? String(it.estimated_price) : '',
            },
          } as unknown as Href)}
        />

        {/* 3c. Browse by Set/Brand — grouped collections, not individual items.
            Dimension is per-category (watches → brand; most → set_code). Each
            tile opens an Instagram-discover grid of that group's items. */}
        <FeaturedCollectionsSection
          categoryId={String(categoryId)}
          collections={[]}
          groupBy={categoryMeta.collectionDimension ?? 'set'}
          title={categoryMeta.collectionDimension === 'brand' ? '🏷 Browse by Brand' : '🗂 Browse by Set'}
          onCollectionPress={(col) => router.push({
            pathname: '/catalog-set/[setCode]',
            params: {
              setCode: col.collection_key,
              category: String(categoryId),
              name: col.display_name,
              dimension: categoryMeta.collectionDimension ?? 'set',
            },
          } as unknown as Href)}
        />

        {/* 4. Category market value — REMOVED 2026-08-11.
            A median across a whole category cannot value the object in front of
            you: "the typical watch is EUR 914" is true and useless when you own
            a Daytona. The mean it replaced was worse (EUR 7,172 for watches,
            7.8x the median; pokemon 21x), but fixing the statistic did not make
            the number answer a question anyone was asking. Removed rather than
            corrected again. */}

        {/* — below the fold — */}

        {/* 5. Upcoming Events & Drops */}
        <CategoryEventsSection
          events={events}
          onEventPress={handleEventPress}
          colors={colors}
        />

        {/* 6. Related Categories — Friends Who Follow is gone; its Invite/
            Find friends CTAs moved into the header banner. */}
        <RelatedCategoriesSection
          categories={relatedCategories}
          onCategoryPress={handleRelatedCategoryPress}
          colors={colors}
        />

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>

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
  setsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginHorizontal: 16,
    marginTop: 10,
    padding: 12,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  guideBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  guideIcon: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: 'center', justifyContent: 'center',
  },
  guideTitle: { fontSize: text.md, fontWeight: fontWeight.bold },
  guideSub: { fontSize: text.sm, lineHeight: 17, marginTop: 2 },
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
