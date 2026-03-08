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

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';

type Props = {
  socialProof: SocialProof;
  currency: CurrencyCode;
};

export function SocialProofSection({ socialProof, currency }: Props) {
  const { colors } = useAppTheme();
  const { collectorCount, isTrending, trendRank, recentSold, scarcity } = socialProof;

  if (collectorCount === 0 && !isTrending && recentSold.length === 0) {
    return null;
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="people-outline" size={18} color={TIFFANY_DARK} />
        <Text style={[styles.title, { color: colors.text }]}>Market Context</Text>
      </View>

      {/* Badges row */}
      <View style={styles.badgesRow}>
        {collectorCount > 0 && (
          <View style={[styles.badge, { backgroundColor: TIFFANY + '15' }]}>
            <Ionicons name="people" size={14} color={TIFFANY_DARK} />
            <Text style={[styles.badgeText, { color: TIFFANY_DARK }]}>
              {collectorCount} collector{collectorCount !== 1 ? 's' : ''}
            </Text>
          </View>
        )}
        {isTrending && (
          <View style={[styles.badge, { backgroundColor: '#F59E0B20' }]}>
            <Ionicons name="trending-up" size={14} color="#F59E0B" />
            <Text style={[styles.badgeText, { color: '#F59E0B' }]}>
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
            <View key={idx} style={styles.soldRow}>
              <View style={[styles.soldDot, { backgroundColor: TIFFANY }]} />
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
      {scarcity.scarcityScore > 0 && (
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
                      ? '#EF4444'
                      : scarcity.scarcityScore >= 0.4
                        ? '#F59E0B'
                        : '#22C55E',
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
}

const styles = StyleSheet.create({
  container: {
    marginTop: 12,
    marginHorizontal: 16,
    padding: 18,
    borderRadius: 16,
    borderWidth: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
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
    borderRadius: 8,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  soldSection: {
    marginTop: 4,
    gap: 6,
  },
  subTitle: {
    fontSize: 12,
    fontWeight: '600',
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
    fontSize: 13,
    fontWeight: '500',
  },
  soldPrice: {
    fontSize: 13,
    fontWeight: '700',
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
    fontSize: 12,
    fontWeight: '600',
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
    fontSize: 11,
    fontWeight: '500',
    fontStyle: 'italic',
  },
});

export default SocialProofSection;
