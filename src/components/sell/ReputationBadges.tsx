/**
 * ReputationBadges — Shows seller/buyer trust scores with star ratings.
 * Extracted from sell/[offerId].tsx.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import type { UserReputation } from '@/data/types';
import { radius, text, fontWeight } from '@/theme/tokens';

// ── StarRating ──────────────────────────────────────────────────────────────

const StarRating = React.memo(function StarRating({ stars, size = 14 }: { stars: number; size?: number }) {
  const { colors } = useAppTheme();
  const fullStars = Math.floor(stars);
  const hasHalf = stars - fullStars >= 0.25;
  return (
    <View style={{ flexDirection: 'row', gap: 1 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Ionicons
          key={i}
          name={i < fullStars ? 'star' : (i === fullStars && hasHalf ? 'star-half' : 'star-outline')}
          size={size}
          color={colors.warning}
        />
      ))}
    </View>
  );
});

// ── Single Badge ────────────────────────────────────────────────────────────

const ReputationBadge = React.memo(function ReputationBadge({
  label,
  reputation,
}: {
  label: string;
  reputation: UserReputation | null;
}) {
  const { colors } = useAppTheme();

  if (!reputation) return null;
  return (
    <View style={[styles.repBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.repLabel, { color: colors.muted }]}>{label}</Text>
      <View style={styles.repRow}>
        {reputation.totalRatings > 0 ? (
          <>
            <StarRating stars={reputation.avgStars} />
            <Text style={[styles.repScore, { color: colors.text }]}>
              {reputation.avgStars.toFixed(1)}
            </Text>
          </>
        ) : (
          <Text style={[styles.repNoRating, { color: colors.muted }]}>No ratings yet</Text>
        )}
      </View>
      <Text style={[styles.repDeals, { color: colors.muted }]}>
        {reputation.completedDeals} deal{reputation.completedDeals !== 1 ? 's' : ''} completed
      </Text>
    </View>
  );
});

// ── Reputation Row ──────────────────────────────────────────────────────────

type Props = {
  isSeller: boolean;
  isBuyer: boolean;
  sellerRep: UserReputation | null;
  buyerRep: UserReputation | null;
};

function ReputationBadgesInner({ isSeller, isBuyer, sellerRep, buyerRep }: Props) {
  return (
    <View style={styles.repRowContainer}>
      <ReputationBadge
        label={isSeller ? 'Your reputation (Seller)' : 'Seller'}
        reputation={sellerRep}
      />
      <ReputationBadge
        label={isBuyer ? 'Your reputation (Buyer)' : 'Buyer'}
        reputation={buyerRep}
      />
    </View>
  );
}

export const ReputationBadges = React.memo(ReputationBadgesInner);

const styles = StyleSheet.create({
  repRowContainer: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  repBadge: {
    flex: 1,
    padding: 10,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  repLabel: {
    fontSize: text.xs,
    fontWeight: fontWeight.medium,
    marginBottom: 4,
  },
  repRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  repScore: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
    marginLeft: 6,
  },
  repNoRating: {
    fontSize: text.sm,
    fontStyle: 'italic',
  },
  repDeals: {
    fontSize: text.xs,
    marginTop: 4,
  },
});
