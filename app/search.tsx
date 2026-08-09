/**
 * Global Unified Search Screen
 * Searches across items, catalog, collectors, events, and categories.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { SkeletonList } from '@/components/Skeleton';
import { SlowLoadNotice } from '@/components/SlowLoadNotice';
import { useSlowLoad } from '@/hooks/useSlowLoad';
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

function SearchScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
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
    } catch {
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

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const totalResults = results
    ? results.items.length + results.catalog.length + results.users.length + results.events.length + results.categories.length
    : 0;

  const hasResults = results && totalResults > 0;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {/* Search Header */}
      <View style={styles.header}>
        <AnimatedPressable onPress={() => safeGoBack(router)} style={styles.backBtn} accessibilityRole="button" accessibilityLabel={t('common.go_back')}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <View style={[styles.searchBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder={t('search.placeholder')}
            placeholderTextColor={colors.muted}
            value={query}
            onChangeText={handleQueryChange}
            autoFocus
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

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
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
              <CatalogSearchResult key={catItem.id} item={catItem} colors={colors} onPress={() => router.push(`/categories/${catItem.category}` as Href)} />
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
        {results && results.categories.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">CATEGORIES</Text>
            {results.categories.map((cat) => (
              <CategorySearchResult key={cat.id} cat={cat} colors={colors} onPress={() => router.push(`/categories/${cat.id}` as Href)} />
            ))}
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
  );
}

export default function SearchScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchScreen />
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
  scrollContent: { paddingHorizontal: 16 },
  loadingContainer: { paddingVertical: 32, alignItems: 'center' },
  emptyContainer: { paddingVertical: 48, alignItems: 'center', gap: 12 },
  emptyText: { fontSize: text.lg },
  section: { marginTop: 20 },
  sectionTitle: { fontSize: text.sm, fontWeight: fontWeight.semibold, letterSpacing: 0.5, marginBottom: 8 },
});
