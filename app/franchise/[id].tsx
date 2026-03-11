/**
 * Franchise Detail — shows items across categories for a given franchise.
 * Route: /franchise/[id]
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { getFranchiseById, type Franchise } from '@/data/franchises';
import { CATEGORY_VISUAL, type CategoryId } from '@/data/categories';
import { CategoryLabels } from '../../types/category';
import { dataProvider } from '@/data';
import logger from '@/utils/logger';

type SectionHeader = { type: 'header'; categoryId: string; label: string };
type ItemRow = { type: 'row'; item: { id: string; name: string; categorySlug: string; imageUrl?: string; estimatedValueEur?: number } };
type ListItem = SectionHeader | ItemRow;

function FranchiseDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();

  const franchise = useMemo(() => getFranchiseById(id ?? ''), [id]);

  const [items, setItems] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadItems = useCallback(async () => {
    if (!franchise) return;
    try {
      const allUserItems = await dataProvider.listItems();
      const catIds = new Set(franchise.categoryIds as string[]);

      // Filter to items in franchise categories, then check attributes
      const categoryItems = allUserItems.filter((item) => catIds.has(item.category));
      const matched = categoryItems.filter((item) => {
        // Include all items from franchise categories (they likely belong to the franchise)
        // If item has attributes, check for franchise match
        if (!item.attributesJson) return true;
        const attrs = item.attributesJson;
        for (const key of franchise.matchKeys) {
          const val = attrs[key];
          if (typeof val === 'string') {
            const lower = val.toLowerCase();
            if (franchise.matchValues.some((mv) => lower.includes(mv))) return true;
          }
        }
        // Include items in franchise-specific categories (e.g., pokemon, marvel_legends)
        // even without matching attributes
        return true;
      });

      // Group by category
      const grouped = new Map<string, typeof matched>();
      for (const item of matched) {
        const arr = grouped.get(item.category) ?? [];
        arr.push(item);
        grouped.set(item.category, arr);
      }

      const result: ListItem[] = [];
      for (const catId of franchise.categoryIds) {
        const catItems = grouped.get(catId);
        if (!catItems?.length) continue;
        const label = CategoryLabels[catId as keyof typeof CategoryLabels] ?? catId;
        result.push({ type: 'header', categoryId: catId, label });
        for (const item of catItems) {
          result.push({
            type: 'row',
            item: {
              id: item.id,
              name: item.name,
              categorySlug: catId,
              imageUrl: item.imageUrl,
              estimatedValueEur: item.price,
            },
          });
        }
      }

      setItems(result);
    } catch (err) {
      logger.warn('[FranchiseDetail] loadItems error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [franchise]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  if (!franchise) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ title: 'Franchise' }} />
        <View style={styles.center}>
          <Text style={{ color: colors.muted }}>Franchise not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  const renderItem = ({ item }: { item: ListItem }) => {
    if (item.type === 'header') {
      const visual = CATEGORY_VISUAL[item.categoryId as CategoryId];
      return (
        <View style={[styles.sectionHeader, { borderBottomColor: colors.border }]}>
          <View style={[styles.sectionDot, { backgroundColor: colors.accent }]} />
          <Text style={[styles.sectionHeaderText, { color: colors.muted }]}>
            {item.label.toUpperCase()}
          </Text>
        </View>
      );
    }

    return (
      <AnimatedPressable
        style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => router.push(`/item/${item.item.id}`)}
        accessibilityRole="button"
        accessibilityLabel={item.item.name}
      >
        <View style={[styles.itemAccent, { backgroundColor: franchise.accentColor }]} />
        <View style={styles.itemContent}>
          <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
            {item.item.name}
          </Text>
          {item.item.estimatedValueEur != null && (
            <Text style={[styles.itemValue, { color: colors.accent }]}>
              {'\u20AC'}{item.item.estimatedValueEur.toFixed(0)}
            </Text>
          )}
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </AnimatedPressable>
    );
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <Stack.Screen
        options={{
          title: franchise.name,
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
        }}
      />

      {/* Franchise header */}
      <View style={[styles.heroRow, { borderBottomColor: colors.border }]}>
        <Ionicons
          name={(franchise.iconName as keyof typeof Ionicons.glyphMap) ?? 'star'}
          size={28}
          color={franchise.accentColor}
        />
        <View style={styles.heroText}>
          <Text style={[styles.heroTitle, { color: colors.text }]}>{franchise.name}</Text>
          <Text style={[styles.heroSub, { color: colors.muted }]}>
            {franchise.categoryIds.length} categories
          </Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={franchise.accentColor} />
        </View>
      ) : (
        <FlashList
          data={items}
          keyExtractor={(item, idx) =>
            item.type === 'header' ? `h-${item.categoryId}` : `i-${item.item.id}-${idx}`
          }
          renderItem={renderItem}
          getItemType={(item) => item.type}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); loadItems(); }}
              tintColor={franchise.accentColor}
            />
          }
          ListEmptyComponent={
            <View style={styles.center}>
              <Ionicons name="search-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                No matching items found. Add items with {franchise.name} attributes to see them here.
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  heroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  heroText: { flex: 1 },
  heroTitle: { fontSize: 20, fontWeight: '700' },
  heroSub: { fontSize: 13, marginTop: 2 },
  list: { padding: 16 },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingTop: 12,
    paddingBottom: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    marginBottom: 4,
  },
  sectionDot: { width: 8, height: 8, borderRadius: 4 },
  sectionHeaderText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.8 },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    paddingLeft: 0,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 6,
    overflow: 'hidden',
  },
  itemAccent: { width: 4, alignSelf: 'stretch', borderTopLeftRadius: 10, borderBottomLeftRadius: 10 },
  itemContent: { flex: 1, marginLeft: 12 },
  itemName: { fontSize: 15, fontWeight: '600' },
  itemValue: { fontSize: 13, marginTop: 2 },
  emptyText: { fontSize: 14, textAlign: 'center', marginTop: 12 },
});

export default function FranchiseDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Franchise Detail">
      <FranchiseDetailScreen />
    </ScreenErrorBoundary>
  );
}
