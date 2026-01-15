import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { getPortfolioItems } from '@/services/collectorsClient';
import type { CollectionStatusInput } from '@/utils/statusScoring';
import ItemStatusInspector from '@/components/ItemStatusInspector';

const ItemStatusDebugScreen: React.FC = () => {
  const [items, setItems] = useState<CollectionStatusInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const raw = await getPortfolioItems();
        if (cancelled) return;

        const mapped: CollectionStatusInput[] = (raw || []).map(
          (it: any) => ({
            id: it.id ?? it.item_id ?? undefined,
            name: it.name ?? it.title ?? null,
            title: it.title ?? it.name ?? null,
            category: it.category ?? it.category_label ?? null,
            value:
              typeof it.estimated_value === 'number'
                ? it.estimated_value
                : it.value ?? null,
            collection: it.collection ?? it.set_name ?? null,
            collection_name: it.collection_name ?? it.collection ?? null,
            set_code: it.set_code ?? null,
            set_size: it.set_size ?? null,
            rarity_score: it.rarity_score ?? null,
          }),
        );

        setItems(mapped);
      } catch (e: any) {
        console.error('[ItemStatusDebug] load error', e);
        if (!cancelled) setError('Could not load items.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // naive grouping: take first collection we find
  const firstCollectionKey =
    items[0]?.collection ??
    items[0]?.collection_name ??
    items[0]?.set_code ??
    items[0]?.category ??
    null;

  const collectionItems =
    firstCollectionKey == null
      ? []
      : items.filter(
          (it) =>
            it.collection === firstCollectionKey ||
            it.collection_name === firstCollectionKey ||
            it.set_code === firstCollectionKey ||
            it.category === firstCollectionKey,
        );

  const currentItemId = collectionItems[0]?.id ?? null;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Item status debug</Text>
        <Text style={styles.subtitle}>
          This screen shows how the per-item status inspector looks when fed
          with a sample collection from your portfolio.
        </Text>

        {loading && (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        )}

        {!loading && error && (
          <View style={styles.center}>
            <Text style={styles.error}>{error}</Text>
          </View>
        )}

        {!loading && !error && collectionItems.length === 0 && (
          <View style={styles.center}>
            <Text style={styles.empty}>
              No items available yet to compute a collection. Add some items
              to test the inspector.
            </Text>
          </View>
        )}

        {!loading && !error && collectionItems.length > 0 && (
          <ItemStatusInspector
            collectionItems={collectionItems}
            currentItemId={currentItemId}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f1f5f9',
  },
  content: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  center: {
    marginTop: 24,
    alignItems: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#0f172a',
  },
  subtitle: {
    marginTop: 4,
    fontSize: 12,
    color: '#4b5563',
  },
  error: {
    fontSize: 13,
    color: '#b91c1c',
  },
  empty: {
    fontSize: 12,
    color: '#6b7280',
    textAlign: 'center',
    paddingHorizontal: 16,
  },
});

export default ItemStatusDebugScreen;
