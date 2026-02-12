import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import type { CollectionLeaderboardEntry } from '@/services/collectorsClient';
import { formatPrice } from '@/lib/format';

type StatusTier = 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Whale';

interface TierMeta {
  tier: StatusTier;
  label: string;
}

export const computeStatusTier = (totalValue: number | null | undefined): TierMeta => {
  const v = typeof totalValue === 'number' && Number.isFinite(totalValue) ? totalValue : 0;

  if (v >= 100_000) return { tier: 'Whale',    label: 'Whale Collector' };
  if (v >= 25_000)  return { tier: 'Platinum', label: 'Platinum Collector' };
  if (v >= 10_000)  return { tier: 'Gold',     label: 'Gold Collector' };
  if (v >= 2_500)   return { tier: 'Silver',   label: 'Silver Collector' };
  return { tier: 'Bronze', label: 'Bronze Collector' };
};

type FraudState = 'verified' | 'review' | 'blocked';

interface FraudMeta {
  state: FraudState;
  label: string;
}

/**
 * Anti-fraud moat heuristic:
 * - trust_score >= 80 and anomaly_count === 0 → verified
 * - trust_score <= 40 or anomaly_count >= 3 or coverage_score < 40 → blocked
 * - everything else → review
 *
 * Backend can later wire trust_score, anomaly_count, coverage_score
 * using Supabase views (v_coverage, item_review_queue, alerts, etc.).
 */
export const computeFraudMeta = (
  entry: CollectionLeaderboardEntry,
): FraudMeta => {
  const trust = entry.trust_score ?? 0;
  const anomalies = entry.anomaly_count ?? 0;
  const coverage = entry.coverage_score ?? 0;

  const lowTrust = trust <= 40;
  const manyAnomalies = anomalies >= 3;
  const lowCoverage = coverage > 0 && coverage < 40;

  if (trust >= 80 && anomalies === 0 && coverage >= 60) {
    return { state: 'verified', label: 'Verified' };
  }

  if (lowTrust || manyAnomalies || lowCoverage) {
    return { state: 'blocked', label: 'Review required' };
  }

  return { state: 'review', label: 'Manual review' };
};

interface Props {
  entry: CollectionLeaderboardEntry;
  compact?: boolean;
}

export const CollectionStatusBadge: React.FC<Props> = ({ entry, compact }) => {
  const tier = computeStatusTier(entry.total_value);
  const fraud = computeFraudMeta(entry);

  return (
    <View style={[styles.row, compact && styles.rowCompact]}>
      <View style={styles.tierPill}>
        <Text style={styles.tierText}>{tier.tier}</Text>
      </View>
      <View style={styles.labelsCol}>
        <Text style={styles.tierLabel}>{tier.label}</Text>
        <Text style={styles.subtle}>
          {entry.item_count ?? 0} items · {formatPrice(entry.total_value)}
        </Text>
      </View>
      <View
        style={[
          styles.fraudPill,
          fraud.state === 'verified' && styles.fraudVerified,
          fraud.state === 'review' && styles.fraudReview,
          fraud.state === 'blocked' && styles.fraudBlocked,
        ]}
      >
        <Text style={styles.fraudText}>{fraud.label}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  rowCompact: {
    paddingVertical: 2,
  },
  tierPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: '#e0f2fe', // light blue
  },
  tierText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0369a1',
  },
  labelsCol: {
    flex: 1,
  },
  tierLabel: {
    fontSize: 13,
    fontWeight: '600',
  },
  subtle: {
    fontSize: 11,
    opacity: 0.7,
  },
  fraudPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  fraudVerified: {
    backgroundColor: '#dcfce7',
  },
  fraudReview: {
    backgroundColor: '#fef9c3',
  },
  fraudBlocked: {
    backgroundColor: '#fee2e2',
  },
  fraudText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#111827',
  },
});

export default CollectionStatusBadge;
