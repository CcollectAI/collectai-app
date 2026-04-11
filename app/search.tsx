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
import { CatalogImage } from '@/components/CatalogImage';
import { radius, text, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

const RECENT_SEARCHES_KEY = '@collectai/recent_searches';
const MAX_RECENT_SEARCHES = 10;

type SearchResults = {
  items: Array<{ id: string; name: string; category: string; imageUrl?: string | null; price?: number }>;
  catalog: Array<{ id: string; category: string; itemKey: string; title: string; brand?: string | null; imageUrl?: string | null }>;
  users: Array<{ id: string; displayName: string; handle?: string; avatarUrl?: string | null }>;
  events: Array<{ id: string; title: string; startDate?: string; location?: string; category?: string }>;
  categories: Array<{ id: string; name: string }>;
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
  return (
    <AnimatedPressable
      style={[resultStyles.resultRow, { borderColor: colors.border }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${item.title} in catalog`}
    >
      <CatalogImage
        uri={item.imageUrl}
        style={resultStyles.resultThumb}
        fallbackIcon="library-outline"
        fallbackBackground={colors.accent + '10'}
        fallbackIconColor={colors.accent}
      />
      <View style={resultStyles.resultInfo}>
        <Text style={[resultStyles.resultTitle, { color: colors.text }]} numberOfLines={1}>{item.title}</Text>
        <Text style={[resultStyles.resultSubtitle, { color: colors.muted }]}>
          {item.brand ? `${item.brand} · ${item.category}` : item.category}
        </Text>
      </View>
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
});

function SearchScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  const [error, setError] = useState(false);

  // Load recent searches from AsyncStorage on mount
  useEffect(() => {
    AsyncStorage.getItem(RECENT_SEARCHES_KEY)
      .then((stored) => {
        if (stored) {
          try {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) setRecentSearches(parsed);
          } catch { /* ignore parse errors */ }
        }
      })
      .catch((err) => logger.warn('[Search] restore recent searches failed:', err));
  }, []);

  const saveRecentSearch = useCallback((q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setRecentSearches((prev) => {
      const filtered = prev.filter((s) => s.toLowerCase() !== trimmed.toLowerCase());
      const updated = [trimmed, ...filtered].slice(0, MAX_RECENT_SEARCHES);
      AsyncStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated))
        .catch((err) => logger.warn('[Search] persist recent searches failed:', err));
      return updated;
    });
  }, []);

  const clearRecentSearches = useCallback(() => {
    setRecentSearches([]);
    AsyncStorage.removeItem(RECENT_SEARCHES_KEY)
      .catch((err) => logger.warn('[Search] clear recent searches failed:', err));
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
      saveRecentSearch(q);
    } catch {
      setResults(null);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [saveRecentSearch]);

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
        <AnimatedPressable onPress={() => router.back()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <View style={[styles.searchBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder="Search items, collectors, events..."
            placeholderTextColor={colors.muted}
            value={query}
            onChangeText={handleQueryChange}
            autoFocus
            returnKeyType="search"
            accessibilityLabel="Search input"
          />
          {query.length > 0 && (
            <AnimatedPressable onPress={() => { setQuery(''); setResults(null); }} accessibilityRole="button" accessibilityLabel="Clear search">
              <Ionicons name="close-circle" size={18} color={colors.muted} />
            </AnimatedPressable>
          )}
        </View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Recent searches — shown when no query and no results */}
        {!query && !results && recentSearches.length > 0 && (
          <View style={styles.section}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">RECENT SEARCHES</Text>
              <AnimatedPressable onPress={clearRecentSearches} accessibilityRole="button" accessibilityLabel="Clear recent searches">
                <Text style={{ color: colors.accent, fontSize: text.sm, fontWeight: fontWeight.semibold }}>Clear</Text>
              </AnimatedPressable>
            </View>
            {recentSearches.map((term, idx) => (
              <AnimatedPressable
                key={`${term}-${idx}`}
                style={[resultStyles.resultRow, { borderColor: colors.border }]}
                onPress={() => { setQuery(term); doSearch(term); }}
                accessibilityRole="button"
                accessibilityLabel={`Search for ${term}`}
              >
                <Ionicons name="time-outline" size={18} color={colors.muted} />
                <View style={resultStyles.resultInfo}>
                  <Text style={[resultStyles.resultTitle, { color: colors.text }]}>{term}</Text>
                </View>
                <Ionicons name="arrow-forward-outline" size={16} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </View>
        )}

        {loading && (
          <View style={styles.loadingContainer}>
            <SkeletonList count={6} />
          </View>
        )}

        {!loading && error && (
          <View style={styles.emptyContainer}>
            <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.emptyText, { color: colors.muted }]}>Search unavailable</Text>
            <AnimatedPressable onPress={() => doSearch(query)} style={{ marginTop: 12, paddingHorizontal: 20, paddingVertical: 10, borderRadius: radius.xs, backgroundColor: colors.accent }} accessibilityRole="button" accessibilityLabel="Retry search">
              <Text style={{ color: colors.accentText, fontWeight: fontWeight.semibold, fontSize: text.md }}>Retry</Text>
            </AnimatedPressable>
          </View>
        )}

        {!loading && !error && query.length > 0 && !hasResults && (
          <View style={styles.emptyContainer}>
            <Ionicons name="search-outline" size={48} color={colors.muted} />
            <Text style={[styles.emptyText, { color: colors.muted }]}>No results found</Text>
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
