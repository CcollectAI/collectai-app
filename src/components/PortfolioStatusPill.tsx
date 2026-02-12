import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { getPortfolioItems } from '@/services/collectorsClient';
import {
  CollectionStatusInput,
  computeCollectionStatusScores,
  computeOverallTier,
} from '@/utils/statusScoring';
import { StatusBadge } from '@/components/StatusBadge';

export const PortfolioStatusPill: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState<'Diamond' | 'Gold' | 'Silver'>('Silver');
  const [avgPoints, setAvgPoints] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const raw = await getPortfolioItems();
        if (cancelled) return;

        const mapped: CollectionStatusInput[] = (raw || []).map((it: Record<string, unknown>) => ({
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

        const scores = computeCollectionStatusScores(mapped);
        const overall = computeOverallTier(scores);
        setTier(overall.tier);
        setAvgPoints(overall.avgPoints);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 10,
          paddingVertical: 4,
          borderRadius: 999,
          backgroundColor: '#e5e7eb',
        }}
      >
        <ActivityIndicator size="small" />
      </View>
    );
  }

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 999,
        backgroundColor: '#e0f2fe',
      }}
    >
      <StatusBadge tier={tier} compact />
      <Text
        style={{
          marginLeft: 6,
          fontSize: 11,
          fontWeight: '600',
          color: '#0369a1',
        }}
      >
        {avgPoints.toFixed(0)} pts
      </Text>
    </View>
  );
};

export default PortfolioStatusPill;
