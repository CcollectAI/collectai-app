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
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { SkeletonList } from '@/components/Skeleton';

type SearchResults = {
  items: Array<{ id: string; name: string; category: string; imageUrl?: string | null; price?: number }>;
  catalog: Array<{ id: string; category: string; itemKey: string; title: string; brand?: string | null; imageUrl?: string | null }>;
  users: Array<{ id: string; displayName: string; handle?: string; avatarUrl?: string | null }>;
  events: Array<{ id: string; title: string; startDate?: string; location?: string; category?: string }>;
  categories: Array<{ id: string; name: string }>;
};

function SearchScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [error, setError] = useState(false);

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
        {loading && (
          <View style={styles.loadingContainer}>
            <SkeletonList count={6} />
          </View>
        )}

        {!loading && error && (
          <View style={styles.emptyContainer}>
            <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.emptyText, { color: colors.muted }]}>Search unavailable</Text>
            <AnimatedPressable onPress={() => doSearch(query)} style={{ marginTop: 12, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8, backgroundColor: colors.accent }} accessibilityRole="button" accessibilityLabel="Retry search">
              <Text style={{ color: '#fff', fontWeight: '600', fontSize: 14 }}>Retry</Text>
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
              <AnimatedPressable
                key={item.id}
                style={[styles.resultRow, { borderColor: colors.border }]}
                onPress={() => router.push(`/item/${item.id}` as never)}
                accessibilityRole="button"
                accessibilityLabel={`View ${item.name}`}
              >
                {item.imageUrl ? (
                  <Image source={{ uri: item.imageUrl }} style={styles.resultThumb} />
                ) : (
                  <View style={[styles.resultThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
                    <Ionicons name="cube-outline" size={18} color={colors.accent} />
                  </View>
                )}
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={1}>{item.name}</Text>
                  <Text style={[styles.resultSubtitle, { color: colors.muted }]}>{item.category}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </View>
        )}

        {/* Catalog Section */}
        {results && results.catalog.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">CATALOG</Text>
            {results.catalog.map((catItem) => (
              <AnimatedPressable
                key={catItem.id}
                style={[styles.resultRow, { borderColor: colors.border }]}
                onPress={() => router.push(`/categories/${catItem.category}` as never)}
                accessibilityRole="button"
                accessibilityLabel={`View ${catItem.title} in catalog`}
              >
                {catItem.imageUrl ? (
                  <Image source={{ uri: catItem.imageUrl }} style={styles.resultThumb} />
                ) : (
                  <View style={[styles.resultThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
                    <Ionicons name="library-outline" size={18} color={colors.accent} />
                  </View>
                )}
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={1}>{catItem.title}</Text>
                  <Text style={[styles.resultSubtitle, { color: colors.muted }]}>
                    {catItem.brand ? `${catItem.brand} · ${catItem.category}` : catItem.category}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </View>
        )}

        {/* Users Section */}
        {results && results.users.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">COLLECTORS</Text>
            {results.users.map((user) => (
              <AnimatedPressable
                key={user.id}
                style={[styles.resultRow, { borderColor: colors.border }]}
                onPress={() => router.push(`/users/${user.id}` as never)}
                accessibilityRole="button"
                accessibilityLabel={`View ${user.displayName}'s profile`}
              >
                {user.avatarUrl ? (
                  <Image source={{ uri: user.avatarUrl }} style={styles.resultAvatar} />
                ) : (
                  <View style={[styles.resultThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
                    <Ionicons name="person-outline" size={18} color={colors.accent} />
                  </View>
                )}
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={1}>{user.displayName}</Text>
                  {user.handle && <Text style={[styles.resultSubtitle, { color: colors.muted }]}>@{user.handle}</Text>}
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </View>
        )}

        {/* Events Section */}
        {results && results.events.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">EVENTS</Text>
            {results.events.map((event) => (
              <AnimatedPressable
                key={event.id}
                style={[styles.resultRow, { borderColor: colors.border }]}
                onPress={() => router.push(`/events/${event.id}` as never)}
                accessibilityRole="button"
                accessibilityLabel={`View ${event.title}`}
              >
                <Ionicons name="calendar-outline" size={20} color={colors.accent} />
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={1}>{event.title}</Text>
                  {event.location && <Text style={[styles.resultSubtitle, { color: colors.muted }]}>{event.location}</Text>}
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </View>
        )}

        {/* Categories Section */}
        {results && results.categories.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]} accessibilityRole="header">CATEGORIES</Text>
            {results.categories.map((cat) => (
              <AnimatedPressable
                key={cat.id}
                style={[styles.resultRow, { borderColor: colors.border }]}
                onPress={() => router.push(`/categories/${cat.id}` as never)}
                accessibilityRole="button"
                accessibilityLabel={`Browse ${cat.name}`}
              >
                <Ionicons name="grid-outline" size={20} color={colors.accent} />
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={1}>{cat.name}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </AnimatedPressable>
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
  searchBar: { flex: 1, flexDirection: 'row', alignItems: 'center', borderRadius: 12, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  searchInput: { flex: 1, fontSize: 16, padding: 0 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16 },
  loadingContainer: { paddingVertical: 32, alignItems: 'center' },
  emptyContainer: { paddingVertical: 48, alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16 },
  section: { marginTop: 20 },
  sectionTitle: { fontSize: 12, fontWeight: '600', letterSpacing: 0.5, marginBottom: 8 },
  resultRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, gap: 12 },
  resultThumb: { width: 36, height: 36, borderRadius: 8 },
  resultAvatar: { width: 36, height: 36, borderRadius: 18 },
  resultThumbPlaceholder: { width: 36, height: 36, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  resultInfo: { flex: 1 },
  resultTitle: { fontSize: 15, fontWeight: '500' },
  resultSubtitle: { fontSize: 13, marginTop: 2 },
});
