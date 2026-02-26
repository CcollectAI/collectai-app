import React, { useEffect, useState, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
  RefreshControl,
} from 'react-native';
import { getPortfolioItems, type PortfolioItem } from '@/services/collectorsClient';
import type { CollectionStatusInput } from '@/utils/statusScoring';
import ItemsStatusPanel from '@/components/ItemsStatusPanel';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';
import { formatPrice } from '@/lib/format';

const ItemsStatusScreen: React.FC = () => {
  const { settings } = useSettings();
  const [items, setItems] = useState<CollectionStatusInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (cancelled = { current: false }) => {
    setLoading(true);
    setError(null);
    try {
      const raw = await getPortfolioItems();
      if (cancelled.current) return;

      const mapped: CollectionStatusInput[] = (raw || []).map((it: PortfolioItem) => ({
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
      }));

      setItems(mapped);
    } catch (e: unknown) {
      logger.error('[ItemsStatusScreen] load error', e);
      if (!cancelled.current) setError('Could not load items for status.');
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  };

  useEffect(() => {
    const cancelled = { current: false };
    load(cancelled);
    return () => {
      cancelled.current = true;
    };
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  };

  const totalValue = useMemo(
    () =>
      items.reduce(
        (sum, it) =>
          sum + (typeof it.value === 'number' ? it.value : 0),
        0,
      ),
    [items],
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor="#81D8D0"
          />
        }
      >
        <View style={styles.header}>
          <Text style={styles.title}>Collection status</Text>
          <Text style={styles.subtitle}>
            Points from completeness (sets finished) and rarity. This screen
            is a status/leaderboard view driven by your Items.
          </Text>
          <Text style={styles.meta}>
            Items: {items.length} · Total value: {formatPrice(totalValue)}
          </Text>
        </View>

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

        {!loading && !error && (
          <ItemsStatusPanel items={items} />
        )}
      </ScrollView>
      <QuickNavBar />
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
  header: {
    marginBottom: 12,
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
  meta: {
    marginTop: 4,
    fontSize: 11,
    color: '#9ca3af',
  },
  center: {
    marginTop: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  error: {
    fontSize: 13,
    color: '#b91c1c',
  },
});

export default function ItemsStatusScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Items Status">
      <ItemsStatusScreen />
    </ScreenErrorBoundary>
  );
}
