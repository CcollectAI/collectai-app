/**
 * SocialProofSection — displays collector count, trending status,
 * recent sold items, and scarcity data on the scan result screen.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import type { SocialProof, CurrencyCode } from '@/data/types';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';

type Props = {
  socialProof: SocialProof;
  currency: CurrencyCode;
};

export const SocialProofSection = React.memo(function SocialProofSection({ socialProof, currency }: Props) {
  const { colors } = useAppTheme();

  if (!socialProof) return null;

  const {
    collectorCount = 0,
    isTrending = false,
    trendRank,
    recentSold = [],
    scarcity,
  } = socialProof;

  const hasScarcity = scarcity != null && scarcity.scarcityScore > 0;

  if (collectorCount === 0 && !isTrending && recentSold.length === 0 && !hasScarcity) {
    return null;
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="people-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Market Context</Text>
      </View>

      {/* Badges row */}
      <View style={styles.badgesRow}>
        {collectorCount > 0 && (
          <View
            style={[styles.badge, { backgroundColor: colors.accent + '15' }]}
            accessibilityLabel={`${collectorCount} collector${collectorCount !== 1 ? 's' : ''} tracking this item`}
          >
            <Ionicons name="people" size={14} color={colors.accent} />
            <Text style={[styles.badgeText, { color: colors.accent }]}>
              {collectorCount} collector{collectorCount !== 1 ? 's' : ''}
            </Text>
          </View>
        )}
        {isTrending && (
          <View
            style={[styles.badge, { backgroundColor: colors.warning + '20' }]}
            accessibilityLabel={`Trending${trendRank ? ` number ${trendRank}` : ''}`}
          >
            <Ionicons name="trending-up" size={14} color={colors.warning} />
            <Text style={[styles.badgeText, { color: colors.warning }]}>
              Trending{trendRank ? ` #${trendRank}` : ''}
            </Text>
          </View>
        )}
      </View>

      {/* Recent sold */}
      {recentSold.length > 0 && (
        <View style={styles.soldSection}>
          <Text style={[styles.subTitle, { color: colors.muted }]}>Recent Sales</Text>
          {recentSold.slice(0, 3).map((sold, idx) => (
            <View key={idx} style={styles.soldRow} accessibilityLabel={`Recent sale: ${sold.title ?? 'Unknown'}, ${sold.price != null ? formatPrice(sold.price, currency) : 'price unknown'}`}>
              <View style={[styles.soldDot, { backgroundColor: colors.accent }]} />
              <Text style={[styles.soldTitle, { color: colors.text }]} numberOfLines={1}>
                {sold.title ?? 'Unknown'}
              </Text>
              <Text style={[styles.soldPrice, { color: colors.text }]}>
                {sold.price != null ? formatPrice(sold.price, currency) : '—'}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Scarcity bar */}
      {hasScarcity && scarcity != null && (
        <View style={styles.scarcitySection}>
          <View style={styles.scarcityHeader}>
            <Text style={[styles.subTitle, { color: colors.muted }]}>Scarcity</Text>
            <Text style={[styles.scarcityLabel, { color: colors.text }]}>
              {scarcity.listingCount} listing{scarcity.listingCount !== 1 ? 's' : ''}
            </Text>
          </View>
          <View style={[styles.scarcityTrack, { backgroundColor: colors.border + '60' }]}>
            <View
              style={[
                styles.scarcityFill,
                {
                  width: `${Math.min(100, scarcity.scarcityScore * 100)}%`,
                  backgroundColor:
                    scarcity.scarcityScore >= 0.7
                      ? colors.danger
                      : scarcity.scarcityScore >= 0.4
                        ? colors.warning
                        : colors.success,
                },
              ]}
            />
          </View>
          <Text style={[styles.scarcityTrend, { color: colors.muted }]}>
            Supply: {scarcity.supplyTrend}
          </Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    marginTop: 12,
    marginHorizontal: 16,
    padding: 18,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  title: {
    fontSize: textToken.lg,
    fontWeight: fw.bold,
    letterSpacing: 0.2,
  },
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.xs,
  },
  badgeText: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
  soldSection: {
    marginTop: 4,
    gap: 6,
  },
  subTitle: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  soldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  soldDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  soldTitle: {
    flex: 1,
    fontSize: textToken.md,
    fontWeight: fw.medium,
  },
  soldPrice: {
    fontSize: textToken.md,
    fontWeight: fw.bold,
  },
  scarcitySection: {
    marginTop: 12,
    gap: 4,
  },
  scarcityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  scarcityLabel: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
  scarcityTrack: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  scarcityFill: {
    height: '100%',
    borderRadius: 3,
  },
  scarcityTrend: {
    fontSize: textToken.sm,
    fontWeight: fw.medium,
    fontStyle: 'italic',
  },
});

export default SocialProofSection;
