import React, { useEffect, useMemo, useState } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  ActivityIndicator,
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
import { useAppTheme } from '@/hooks/useAppTheme';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { UpgradePrompt } from '@/components/UpgradePrompt';

const MIN_COMPLETENESS = 0.4;
const MAX_COMPLETENESS = 0.95;

const SetsToCompleteScreen: React.FC = () => {
  const { colors } = useAppTheme();
  const { limits } = useBillingLimits();
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
          id: it.id ?? (it.item_id as string | undefined) ?? undefined,
          name: it.name ?? (it.title as string | null) ?? null,
          title: (it.title as string | null) ?? it.name ?? null,
          category: it.category ?? (it.category_label as string | null) ?? null,
          value:
            typeof it.estimated_value === 'number'
              ? it.estimated_value
              : (it.value as number | null) ?? null,
          collection: (it.collection as string | null) ?? (it.set_name as string | null) ?? null,
          collection_name: (it.collection_name as string | null) ?? (it.collection as string | null) ?? null,
          set_code: (it.set_code as string | null) ?? null,
          set_size: (it.set_size as number | null) ?? null,
          rarity_score: (it.rarity_score as number | null) ?? null,
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
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={[styles.title, { color: colors.text }]}>Sets to complete</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
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

        {!loading && !error && !limits.set_completion && (
          <UpgradePrompt feature="Set Completion Tracking" requiredPlan="Pro" />
        )}

        {!loading && !error && limits.set_completion && candidates.length === 0 && (
          <View style={styles.center}>
            <Text style={styles.empty}>
              No sets are near completion yet. Add more items or scan your
              existing cards, figures, and sets.
            </Text>
          </View>
        )}

        {!loading &&
          !error &&
          limits.set_completion &&
          candidates.map((s) => {
            const missing = Math.max(
              0,
              s.expectedCount - s.ownedCount,
            );
            return (
              <View key={s.key} style={[styles.card, { backgroundColor: colors.card }]}>
                <Text style={[styles.cardTitle, { color: colors.text }]}>{s.key}</Text>
                <Text style={[styles.cardMeta, { color: colors.muted }]}>
                  {s.category} · {s.ownedCount}/{s.expectedCount} items
                </Text>
                <Text style={[styles.cardRow, { color: colors.text }]}>
                  Completeness:{' '}
                  {Math.round(s.completenessRatio * 100)}%
                </Text>
                <Text style={[styles.cardRow, { color: colors.text }]}>
                  Missing items: {missing}
                </Text>
                <Text style={[styles.cardRow, { color: colors.text }]}>
                  Estimated value: {formatPrice(s.valueTotal)}
                </Text>
              </View>
            );
          })}
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
  },
  subtitle: {
    marginTop: 4,
    fontSize: 12,
  },
  error: {
    fontSize: 13,
    color: '#b91c1c',
  },
  empty: {
    fontSize: 12,
    textAlign: 'center',
    paddingHorizontal: 16,
  },
  card: {
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
  },
  cardMeta: {
    marginTop: 2,
    fontSize: 11,
  },
  cardRow: {
    marginTop: 4,
    fontSize: 11,
  },
});

export default function SetsToCompleteScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sets to Complete">
      <SetsToCompleteScreen />
    </ScreenErrorBoundary>
  );
}
