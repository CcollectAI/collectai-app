/**
 * Categories List — Browse categories with completion stats.
 * Route: /categories
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  TextInput,
  Image,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  Pressable,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Stack, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategorySummary } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';
import { QuickNavBar } from '@/components/QuickNavBar';
import { CATEGORY_VISUAL, CATEGORY_GROUPS, getCategoryById, type CategoryId } from '@/data/categories';
import { formatCategoryName } from '@/constants/categories';
import { FRANCHISES } from '@/data/franchises';
import { useTranslation } from 'react-i18next';

type GroupHeader = { type: 'header'; label: string };
type CategoryRow = { type: 'row'; summary: CategorySummary };
type ListItem = GroupHeader | CategoryRow;

/**
 * Display label for a category id.
 *
 * `v_category_summaries_v1` sets `name = category`, i.e. the raw slug, so this
 * screen was rendering `action_figures` / `anime_bluray` verbatim in card titles,
 * accessibility labels and the search filter. Prefer the curated name from
 * `@/data/categories` (`pokemon` → "Pokémon Cards", `lorcana` → "Disney
 * Lorcana"), and title-case the slug for the tail of the 54 categories that has
 * no curated entry — the same contract `formatCategoryName` documents
 * ("raw values never surface underscored/lowercase in the UI").
 */
function categoryLabel(id: string): string {
  return getCategoryById(id as CategoryId)?.name ?? formatCategoryName(id);
}

export default function CategoriesListScreenWithBoundary() {
  const { t } = useTranslation();
  return (
    <ScreenErrorBoundary screenName="Categories">
      {/* Registered with iconOnlyHeader (headerTitle ''), and the body opens on
          a search box — so the screen had NO title anywhere (seen 2026-09-15).
          Set here, above every branch, so loading/error/list all carry it. */}
      <Stack.Screen options={{ headerTitle: t('screen_titles.categories') }} />
      <CategoriesListScreen />
    </ScreenErrorBoundary>
  );
}

function CategoriesListScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [activeFranchise, setActiveFranchise] = useState<string | null>(null);

  const loadCategories = useCallback(async () => {
    try {
      setError(null);
      const data = await dataProvider.listCategorySummaries();
      setCategories(data);
    } catch (err: unknown) {
      logger.error('[CategoriesList] loadCategories error:', err);
      // A sentence, not err.message ("Request timed out after 15000ms").
      setError(t('category.list_load_failed', { defaultValue: "Couldn't load categories" }));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [t]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadCategories();
  };

  const franchiseCategoryIds = useMemo<Set<string> | null>(() => {
    if (!activeFranchise) return null;
    const f = FRANCHISES.find((fr) => fr.id === activeFranchise);
    return f ? new Set(f.categoryIds) : null;
  }, [activeFranchise]);

  const listData = useMemo<ListItem[]>(() => {
    const q = search.trim().toLowerCase();
    const catById = new Map(categories.map((c) => [c.id, c]));
    const placed = new Set<string>();
    const items: ListItem[] = [];

    for (const group of CATEGORY_GROUPS) {
      const rows: CategoryRow[] = [];
      for (const id of group.ids) {
        const summary = catById.get(id);
        if (!summary) continue;
        if (q && !categoryLabel(summary.id).toLowerCase().includes(q)) continue;
        if (franchiseCategoryIds && !franchiseCategoryIds.has(id)) continue;
        rows.push({ type: 'row', summary });
        placed.add(id);
      }
      if (rows.length > 0) {
        items.push({ type: 'header', label: group.label });
        items.push(...rows);
      }
    }

    // Append ungrouped categories as fallback
    const ungrouped: CategoryRow[] = [];
    for (const c of categories) {
      if (placed.has(c.id)) continue;
      if (q && !categoryLabel(c.id).toLowerCase().includes(q)) continue;
      if (franchiseCategoryIds && !franchiseCategoryIds.has(c.id)) continue;
      ungrouped.push({ type: 'row', summary: c });
    }
    if (ungrouped.length > 0) {
      items.push({ type: 'header', label: 'Other' });
      items.push(...ungrouped);
    }

    return items;
  }, [categories, search, franchiseCategoryIds]);

  // Track failed image loads to show icon fallback
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set());

  const renderItem = ({ item }: { item: ListItem }) => {
    if (item.type === 'header') {
      return (
        <View style={[styles.groupHeader, { borderBottomColor: colors.border }]}>
          <Text style={[styles.groupHeaderText, { color: colors.muted }]}>
            {item.label.toUpperCase()}
          </Text>
        </View>
      );
    }

    const cat = item.summary;
    const visual = CATEGORY_VISUAL[cat.id as CategoryId];
    const iconName = (visual?.iconName ?? 'grid-outline') as keyof typeof Ionicons.glyphMap;
    const catData = getCategoryById(cat.id as CategoryId);
    const bannerUrl = catData?.bannerImageUrl;
    const showImage = bannerUrl && !failedImages.has(cat.id);
    const progressColor = cat.completionPct >= 75
      ? colors.success
      : cat.completionPct >= 50
        ? colors.warning
        : colors.accent;

    return (
      <AnimatedPressable
        style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => router.push(`/categories/${encodeURIComponent(cat.id)}`)}
        accessibilityRole="button"
        accessibilityLabel={`${categoryLabel(cat.id)}, ${cat.completionPct}% complete, ${cat.missingCount} missing`}
      >
        {/* Category thumbnail */}
        {showImage ? (
          <Image
            source={{ uri: bannerUrl }}
            style={[styles.categoryImage, { borderColor: colors.accent }]}
            accessibilityIgnoresInvertColors
            onError={() => setFailedImages((prev) => new Set(prev).add(cat.id))}
          />
        ) : (
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name={iconName} size={24} color={colors.accent} />
          </View>
        )}

        <View style={styles.cardContent}>
          <Text style={[styles.cardTitle, { color: colors.text }]} numberOfLines={1}>
            {categoryLabel(cat.id)}
          </Text>

          {/* Progress bar */}
          <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
            <View
              style={[
                styles.progressFill,
                { backgroundColor: progressColor, width: `${Math.min(cat.completionPct, 100)}%` },
              ]}
            />
          </View>

          {/* Compact stats */}
          <View style={styles.statsRow}>
            <Text style={[styles.statText, { color: colors.text, fontWeight: '700' }]}>
              {cat.completionPct}%
            </Text>
            <View style={styles.statsRight}>
              <Text style={[styles.ownedStat, { color: colors.success }]}>
                {cat.ownedCount}
              </Text>
              {/* muted, not border: in `border` the slash vanished on the card
                  and "2 / 20478" read as two unrelated numbers. */}
              <Text style={[styles.statSep, { color: colors.muted }]}>/</Text>
              <Text style={[styles.totalStat, { color: colors.muted }]}>
                {cat.totalCount}
              </Text>
            </View>
          </View>
        </View>

        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </AnimatedPressable>
    );
  };

  const getItemType = (item: ListItem) => (item.type === 'header' ? 'header' : 'row');

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
        <QuickNavBar />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>

      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          {/* The sentence IS the title. It used to sit under a hardcoded
              English "Error", with err.message as the body. */}
          <Text style={[styles.errorText, { color: colors.text }]}>{error}</Text>
          <AnimatedPressable
            style={[styles.retryBtn, { backgroundColor: colors.accent }]}
            // setLoading first: loadCategories clears `error` before it fetches,
            // so without the spinner the screen fell through to the list branch
            // with no categories for the length of the retry.
            onPress={() => { setLoading(true); loadCategories(); }}
            accessibilityRole="button"
            accessibilityLabel={t('category.a11y_retry_categories', { defaultValue: 'Retry loading categories' })}
          >
            <Text style={[styles.retryBtnText, { color: colors.accentText }]}>{t('common.retry', { defaultValue: 'Retry' })}</Text>
          </AnimatedPressable>
        </View>
      ) : (
        <>
          {/* Search bar */}
          <View style={[styles.searchContainer, { borderBottomColor: colors.border }]}>
            <Ionicons name="search-outline" size={18} color={colors.muted} />
            <TextInput
              style={[styles.searchInput, { color: colors.text }]}
              placeholder={t('category_picker.search_placeholder', { defaultValue: 'Search categories...' })}
              placeholderTextColor={colors.muted}
              value={search}
              onChangeText={setSearch}
              autoCorrect={false}
              autoCapitalize="none"
              returnKeyType="search"
              accessibilityLabel={t('category_picker.search_a11y', { defaultValue: 'Search categories' })}
            />
            {search.length > 0 && (
              <AnimatedPressable onPress={() => setSearch('')} accessibilityLabel={t('common.clear_search', { defaultValue: 'Clear search' })}>
                <Ionicons name="close-circle" size={18} color={colors.muted} />
              </AnimatedPressable>
            )}
          </View>

          {/* Franchise filter pills */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            // flexGrow: 0 — the same fix CategorySortChips carries. A horizontal
            // ScrollView defaults to flexGrow: 1, so in this flex column it took
            // space from the FlashList below and stretched every pill to ~340dp:
            // tall empty cards reading "Star Wars", "Marvel / MCU" (walked on
            // Android 2026-09-14).
            style={styles.franchisePillsScroll}
            contentContainerStyle={styles.franchisePillsContainer}
          >
            {FRANCHISES.map((fr) => {
              const isActive = activeFranchise === fr.id;
              return (
                <Pressable
                  key={fr.id}
                  onPress={() => setActiveFranchise(isActive ? null : fr.id)}
                  style={[
                    styles.franchisePill,
                    {
                      backgroundColor: isActive ? fr.accentColor : colors.card,
                      borderColor: isActive ? fr.accentColor : colors.border,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: isActive }}
                  accessibilityLabel={`Filter by ${fr.name}`}
                >
                  <View style={[styles.franchiseDot, { backgroundColor: isActive ? colors.accentText : fr.accentColor }]} />
                  <Text style={[styles.franchisePillText, { color: isActive ? colors.accentText : colors.text }]}>
                    {fr.name}
                  </Text>
                  {isActive && (
                    <Ionicons name="close-circle" size={14} color={colors.accentText} />
                  )}
                </Pressable>
              );
            })}
          </ScrollView>

          <FlashList
            data={listData}
            keyExtractor={(item, index) =>
              item.type === 'header' ? `header-${item.label}` : `row-${item.summary.id}`
            }
            renderItem={renderItem}
            getItemType={getItemType}
            contentContainerStyle={styles.list}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={handleRefresh}
                tintColor={colors.accent}
              />
            }
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Ionicons name="grid-outline" size={48} color={colors.muted} />
                <Text style={[styles.emptyText, { color: colors.muted }]}>
                  {search ? 'No matching categories' : 'No categories found'}
                </Text>
              </View>
            }
          />
        </>
      )}
      <QuickNavBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  franchisePillsScroll: {
    flexGrow: 0,
  },
  franchisePillsContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  franchisePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 16,
    borderWidth: 1,
  },
  franchiseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  franchisePillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    paddingVertical: 4,
  },
  list: {
    padding: 16,
  },
  groupHeader: {
    paddingTop: 12,
    paddingBottom: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    marginBottom: 4,
  },
  groupHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderRadius: 14,
    borderWidth: 1,
    marginBottom: 8,
    gap: 12,
  },
  categoryImage: {
    width: 48,
    height: 48,
    borderRadius: 12,
    borderWidth: 2,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardContent: {
    flex: 1,
    gap: 5,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  progressTrack: {
    height: 5,
    borderRadius: 3,
  },
  progressFill: {
    height: 5,
    borderRadius: 3,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statText: {
    fontSize: 13,
  },
  statsRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ownedStat: {
    fontSize: 12,
    fontWeight: '700',
  },
  statSep: {
    fontSize: 12,
    marginHorizontal: 2,
  },
  totalStat: {
    fontSize: 12,
    fontWeight: '500',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 60,
  },
  emptyText: {
    fontSize: 16,
    marginTop: 12,
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  errorText: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 12,
  },
  retryBtn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryBtnText: {
    fontWeight: '600' as const,
  },
});
