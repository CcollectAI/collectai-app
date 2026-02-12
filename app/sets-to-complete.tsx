import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { getPortfolioItems, type PortfolioItem } from '@/services/collectorsClient';
import {
  CollectionStatusInput,
  computeCollectionStatusScores,
  CollectionStatusScore,
} from '@/utils/statusScoring';
import logger from '@/utils/logger';
import { formatPrice } from '@/lib/format';

const MIN_COMPLETENESS = 0.4;
const MAX_COMPLETENESS = 0.95;

const SetsToCompleteScreen: React.FC = () => {
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
        logger.error('[SetsToComplete] load error', e);
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

  const candidates: CollectionStatusScore[] = useMemo(() => {
    if (!items.length) return [];
    const scores = computeCollectionStatusScores(items);
    return scores
      .filter(
        (s) =>
          s.completenessRatio >= MIN_COMPLETENESS &&
          s.completenessRatio <= MAX_COMPLETENESS &&
          s.expectedCount > 0,
      )
      .sort(
        (a, b) =>
          b.completenessRatio - a.completenessRatio ||
          b.valueTotal - a.valueTotal,
      );
  }, [items]);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Sets to complete</Text>
        <Text style={styles.subtitle}>
          Collections that are close to 100% complete. Use this view to decide
          what to hunt for next when searching or buying.
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

        {!loading && !error && candidates.length === 0 && (
          <View style={styles.center}>
            <Text style={styles.empty}>
              No sets are near completion yet. Add more items or scan your
              existing cards, figures, and sets.
            </Text>
          </View>
        )}

        {!loading &&
          !error &&
          candidates.map((s) => {
            const missing = Math.max(
              0,
              s.expectedCount - s.ownedCount,
            );
            return (
              <View key={s.key} style={styles.card}>
                <Text style={styles.cardTitle}>{s.key}</Text>
                <Text style={styles.cardMeta}>
                  {s.category} · {s.ownedCount}/{s.expectedCount} items
                </Text>
                <Text style={styles.cardRow}>
                  Completeness:{' '}
                  {Math.round(s.completenessRatio * 100)}%
                </Text>
                <Text style={styles.cardRow}>
                  Missing items: {missing}
                </Text>
                <Text style={styles.cardRow}>
                  Estimated value: {formatPrice(s.valueTotal)}
                </Text>
              </View>
            );
          })}
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
  card: {
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#ffffff',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0f172a',
  },
  cardMeta: {
    marginTop: 2,
    fontSize: 11,
    color: '#6b7280',
  },
  cardRow: {
    marginTop: 4,
    fontSize: 11,
    color: '#111827',
  },
});

export default SetsToCompleteScreen;
