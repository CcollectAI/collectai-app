/**
 * Categories List — Browse categories with completion stats.
 * Route: /categories
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategorySummary } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';

export default function CategoriesListScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();

  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCategories = useCallback(async () => {
    try {
      setError(null);
      const data = await dataProvider.listCategorySummaries();
      setCategories(data);
    } catch (err: unknown) {
      logger.warn('[CategoriesList] loadCategories error:', err);
      setError(err?.message || 'Failed to load categories');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadCategories();
  };

  const renderCategory = ({ item }: { item: CategorySummary }) => {
    const progressColor = item.completionPct >= 75
      ? '#22c55e'
      : item.completionPct >= 50
        ? '#eab308'
        : colors.accent;

    return (
      <AnimatedPressable
        style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => router.push(`/categories/${encodeURIComponent(item.id)}`)}
        accessibilityRole="button"
        accessibilityLabel={`${item.name}, ${item.completionPct}% complete, ${item.missingCount} missing`}
      >
        <View style={styles.cardContent}>
          <Text style={[styles.cardTitle, { color: colors.text }]} numberOfLines={1}>
            {item.name}
          </Text>

          {/* Progress bar */}
          <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
            <View
              style={[
                styles.progressFill,
                { backgroundColor: progressColor, width: `${item.completionPct}%` },
              ]}
            />
          </View>

          {/* Stats row */}
          <View style={styles.statsRow}>
            <Text style={[styles.statText, { color: colors.muted }]}>
              {item.completionPct}% complete
            </Text>
            <Text style={[styles.statText, { color: colors.accent }]}>
              {item.missingCount} missing
            </Text>
          </View>

          {/* Counts */}
          <View style={styles.countsRow}>
            <View style={styles.countItem}>
              <Ionicons name="checkmark-circle" size={14} color="#22c55e" />
              <Text style={[styles.countText, { color: colors.text }]}>{item.ownedCount}</Text>
            </View>
            <View style={styles.countItem}>
              <Ionicons name="ellipse-outline" size={14} color={colors.muted} />
              <Text style={[styles.countText, { color: colors.text }]}>{item.missingCount}</Text>
            </View>
            <View style={styles.countItem}>
              <Ionicons name="cube-outline" size={14} color={colors.muted} />
              <Text style={[styles.countText, { color: colors.text }]}>{item.totalCount}</Text>
            </View>
          </View>
        </View>

        <Ionicons name="chevron-forward" size={20} color={colors.muted} style={styles.chevron} />
      </AnimatedPressable>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>

      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorText, { color: colors.text }]}>Error</Text>
          <Text style={[styles.errorMessage, { color: colors.muted }]}>{error}</Text>
          <AnimatedPressable
            style={[styles.retryBtn, { backgroundColor: colors.accent }]}
            onPress={loadCategories}
            accessibilityRole="button"
            accessibilityLabel="Retry loading categories"
          >
            <Text style={styles.retryBtnText}>Retry</Text>
          </AnimatedPressable>
        </View>
      ) : (
        <FlatList
          data={categories}
          keyExtractor={(item) => item.id}
          renderItem={renderCategory}
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
              <Text style={[styles.emptyText, { color: colors.muted }]}>No categories found</Text>
            </View>
          }
        />
      )}
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
  list: {
    padding: 16,
    gap: 12,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  cardContent: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  progressTrack: {
    height: 6,
    borderRadius: 3,
    marginBottom: 8,
  },
  progressFill: {
    height: 6,
    borderRadius: 3,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  statText: {
    fontSize: 12,
  },
  countsRow: {
    flexDirection: 'row',
    gap: 16,
  },
  countItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  countText: {
    fontSize: 13,
  },
  chevron: {
    marginLeft: 12,
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
  errorMessage: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 16,
  },
  retryBtn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#fff',
    fontWeight: '600',
  },
});
