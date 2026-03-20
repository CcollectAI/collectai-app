/**
 * PortfolioTierBadge — Displays portfolio tier (Diamond/Gold/Silver) with scores.
 * Extracted from analytics.tsx.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { ScoreExplanationSheet } from '@/components/ScoreExplanationSheet';
import type { PortfolioTierSummary } from '@/analytics/portfolioMetrics';
import { BETA_MODE } from '@/config/featureFlags';
import { radius, text, fontWeight, shadow } from '@/theme/tokens';

const COLORS = {
  card: '#FFFFFF',
  navy: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  tiffanyDark: '#5FBFB6',
};

const TIER_COLORS: Record<string, string> = {
  Diamond: '#A78BFA',
  Gold: '#FBBF24',
  Silver: '#94A3B8',
  Unranked: '#64748B',
};

const TIER_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Diamond: 'diamond-outline',
  Gold: 'trophy-outline',
  Silver: 'medal-outline',
  Unranked: 'help-circle-outline',
};

function formatScore(s: number): string {
  return `${Math.round(s * 100)}`;
}

type Props = {
  tierSummary: PortfolioTierSummary;
};

function PortfolioTierBadgeInner({ tierSummary }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const [scoreSheetVisible, setScoreSheetVisible] = useState(false);

  return (
    <>
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>Portfolio Tier</Text>
        </View>

        <AnimatedPressable
          style={styles.tierBadgeContainer}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); if (!BETA_MODE) router.push('/leaderboard'); }}
          accessibilityRole="button"
          accessibilityLabel={`${tierSummary.tier} tier — view leaderboard`}
        >
          <View style={[styles.tierBadge, { backgroundColor: TIER_COLORS[tierSummary.tier] + '20' }]}>
            <Ionicons
              name={TIER_ICONS[tierSummary.tier]}
              size={28}
              color={TIER_COLORS[tierSummary.tier]}
            />
            <Text style={[styles.tierLabel, { color: TIER_COLORS[tierSummary.tier] }]}>
              {tierSummary.tier}
            </Text>
            <Ionicons
              name="chevron-forward"
              size={16}
              color={TIER_COLORS[tierSummary.tier]}
              style={{ marginLeft: 4 }}
            />
          </View>
          <Text style={styles.tierTapHint}>Tap to view leaderboard</Text>
        </AnimatedPressable>

        <View style={styles.scoresRow}>
          <View style={styles.scoreItem}>
            <Text style={styles.scoreValue}>{formatScore(tierSummary.rarityScore)}</Text>
            <Text style={styles.scoreLabel}>Rarity</Text>
          </View>
          <View style={styles.scoreDivider} />
          <View style={styles.scoreItem}>
            <Text style={styles.scoreValue}>{formatScore(tierSummary.completenessScore)}</Text>
            <Text style={styles.scoreLabel}>Completeness</Text>
          </View>
          <View style={styles.scoreDivider} />
          <View style={styles.scoreItem}>
            <Text style={styles.scoreValue}>{formatScore(tierSummary.diversificationScore)}</Text>
            <Text style={styles.scoreLabel}>Diversity</Text>
          </View>
        </View>

        <AnimatedPressable
          style={styles.whyScoresBtn}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); setScoreSheetVisible(true); }}
          accessibilityRole="button"
          accessibilityLabel="How are scores calculated?"
        >
          <Ionicons name="help-circle-outline" size={16} color={colors.accent} />
          <Text style={styles.whyScoresText}>How are these scores calculated?</Text>
        </AnimatedPressable>
      </View>

      <ScoreExplanationSheet
        visible={scoreSheetVisible}
        onClose={() => setScoreSheetVisible(false)}
        rarityScore={tierSummary.rarityScore}
        completenessScore={tierSummary.completenessScore}
        diversificationScore={tierSummary.diversificationScore}
        tier={tierSummary.tier}
      />
    </>
  );
}

export const PortfolioTierBadge = React.memo(PortfolioTierBadgeInner);

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 16,
    ...shadow.card,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    color: COLORS.navy,
  },
  tierBadgeContainer: {
    alignItems: 'center',
    marginBottom: 20,
  },
  tierBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: radius.xl,
  },
  tierLabel: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
  },
  tierTapHint: {
    fontSize: text.sm,
    color: COLORS.muted,
    marginTop: 6,
  },
  scoresRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreItem: {
    alignItems: 'center',
    flex: 1,
  },
  scoreValue: {
    fontSize: text['2xl'],
    fontWeight: fontWeight.extrabold,
    color: COLORS.navy,
  },
  scoreLabel: {
    fontSize: text.sm,
    color: COLORS.muted,
    marginTop: 2,
  },
  scoreDivider: {
    width: 1,
    height: 32,
    backgroundColor: COLORS.border,
  },
  whyScoresBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  whyScoresText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    color: COLORS.tiffanyDark,
  },
});
