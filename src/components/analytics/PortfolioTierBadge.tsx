/**
 * PortfolioTierBadge — Displays portfolio tier (Diamond/Gold/Silver) with scores.
 * Extracted from analytics.tsx.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, type Href } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { ScoreExplanationSheet } from '@/components/ScoreExplanationSheet';
import type { PortfolioTierSummary } from '@/analytics/portfolioMetrics';
import { BETA_MODE, COMMUNITY_GATED } from '@/config/featureFlags';
import { TIER_COLORS, TIER_ICONS, TIER_LABEL_KEYS } from '@/analytics/tier';
import { radius, text, fontWeight, shadow } from '@/theme/tokens';
import { useTranslation } from 'react-i18next';

// Colors now sourced from useAppTheme() — see component body.
// The tier vocabulary is shared with the Items tab: src/analytics/tier.ts.

/**
 * A score with NO evidence behind it is `—`, not `0`.
 *
 * Rarity and completeness are both averages over the items we could actually
 * read. When that set is empty the honest render is a dash: "0" is a claim
 * that the collection scored zero, which is a different sentence from "we
 * cannot score this yet" (docs/ui-playbook.md, "A number you do not have yet
 * is not zero"). Diversification is always computed from allocations, so it
 * never takes this branch.
 */
function formatScore(s: number, coverage?: { known: number }): string {
  if (coverage && coverage.known === 0) return '—';
  return `${Math.round(s * 100)}`;
}

type Props = {
  tierSummary: PortfolioTierSummary;
  /**
   * Which category board to open (2026-09-18).
   *
   * This badge used to push `/leaderboard` with no param, which renders the
   * **XP** board — and XP is not a shipped feature: `GAMIFICATION_UI_ENABLED`
   * is false and `UserStatsSection` hides XP on a profile for that reason. One
   * screen presented XP as a feature while another deliberately hid it, and on
   * production the board was one stranger's row (50 XP, level 1) because only
   * one account has any XP at all.
   *
   * The category board ranks real collections — items owned or value held —
   * and tells a member "you are #N of M", which the XP board never did.
   * Undefined when the member holds nothing yet: the badge then does not link
   * anywhere, rather than opening a board with nothing to rank.
   */
  leaderboardCategoryId?: string;
};

function PortfolioTierBadgeInner({ tierSummary, leaderboardCategoryId }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const { t } = useTranslation();
  const [scoreSheetVisible, setScoreSheetVisible] = useState(false);

  return (
    <>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.cardHeader}>
          <Text style={[styles.cardTitle, { color: colors.text }]}>{t('analytics.portfolio_tier', { defaultValue: 'Portfolio Tier' })}</Text>
        </View>

        {/* When BETA_MODE or COMMUNITY_GATED, the leaderboard is hidden
            (1-entry leaderboard looks like a ghost town). Render as a
            non-tappable badge so we don't dangle a tap hint that does
            nothing. Routes remain reachable by deep link. */}
        {(BETA_MODE || COMMUNITY_GATED) ? (
          <View style={styles.tierBadgeContainer}>
            <View style={[styles.tierBadge, { backgroundColor: TIER_COLORS[tierSummary.tier] + '20' }]}>
              <Ionicons
                name={TIER_ICONS[tierSummary.tier] as keyof typeof Ionicons.glyphMap}
                size={28}
                color={TIER_COLORS[tierSummary.tier]}
              />
              <Text style={[styles.tierLabel, { color: TIER_COLORS[tierSummary.tier] }]}>
                {t(TIER_LABEL_KEYS[tierSummary.tier], { defaultValue: tierSummary.tier })}
              </Text>
            </View>
          </View>
        ) : (
          <AnimatedPressable
            style={styles.tierBadgeContainer}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              // The CATEGORY board, never the XP one — see `leaderboardCategoryId`.
              if (!leaderboardCategoryId) return;
              router.push(`/leaderboard?categoryId=${encodeURIComponent(leaderboardCategoryId)}` as Href);
            }}
            accessibilityRole="button"
            accessibilityLabel={`${tierSummary.tier} tier — view leaderboard`}
          >
            <View style={[styles.tierBadge, { backgroundColor: TIER_COLORS[tierSummary.tier] + '20' }]}>
              <Ionicons
                name={TIER_ICONS[tierSummary.tier] as keyof typeof Ionicons.glyphMap}
                size={28}
                color={TIER_COLORS[tierSummary.tier]}
              />
              <Text style={[styles.tierLabel, { color: TIER_COLORS[tierSummary.tier] }]}>
                {t(TIER_LABEL_KEYS[tierSummary.tier], { defaultValue: tierSummary.tier })}
              </Text>
              <Ionicons
                name="chevron-forward"
                size={16}
                color={TIER_COLORS[tierSummary.tier]}
                style={{ marginLeft: 4 }}
              />
            </View>
            <Text style={[styles.tierTapHint, { color: colors.muted }]}>{t('analytics.tap_view_leaderboard', { defaultValue: 'Tap to view leaderboard' })}</Text>
          </AnimatedPressable>
        )}

        <View style={styles.scoresRow}>
          <View style={styles.scoreItem}>
            <Text style={[styles.scoreValue, { color: colors.text }]}>
              {formatScore(tierSummary.rarityScore, tierSummary.rarityCoverage)}
            </Text>
            <Text style={[styles.scoreLabel, { color: colors.muted }]}>{t('analytics.score_rarity', { defaultValue: 'Rarity' })}</Text>
          </View>
          <View style={[styles.scoreDivider, { backgroundColor: colors.border }]} />
          <View style={styles.scoreItem}>
            <Text style={[styles.scoreValue, { color: colors.text }]}>
              {formatScore(tierSummary.completenessScore, tierSummary.completenessCoverage)}
            </Text>
            <Text style={[styles.scoreLabel, { color: colors.muted }]}>{t('analytics.score_completeness', { defaultValue: 'Completeness' })}</Text>
          </View>
          <View style={[styles.scoreDivider, { backgroundColor: colors.border }]} />
          <View style={styles.scoreItem}>
            <Text style={[styles.scoreValue, { color: colors.text }]}>{formatScore(tierSummary.diversificationScore)}</Text>
            <Text style={[styles.scoreLabel, { color: colors.muted }]}>{t('analytics.score_diversity', { defaultValue: 'Diversity' })}</Text>
          </View>
        </View>

        {/* WHAT THE SCORES ARE BUILT ON.
            A rarity of 62 over 3 of 200 items and the same 62 over 190 of 200
            are different claims. The card states which it is holding, rather
            than printing a number that looks equally certain either way. */}
        <Text style={[styles.coverageLine, { color: colors.muted }]}>
          {t('analytics.tier_coverage', {
            defaultValue:
              'Rarity from {{rarityKnown}} of {{rarityTotal}} items · set completion from {{setsKnown}} of {{setsTotal}} sets',
            rarityKnown: tierSummary.rarityCoverage.known,
            rarityTotal: tierSummary.rarityCoverage.total,
            setsKnown: tierSummary.completenessCoverage.known,
            setsTotal: tierSummary.completenessCoverage.total,
          })}
        </Text>

        {/* "Unranked" is not last place, and it is the COMMON case for a new
            collection. Say what would move it, the way a null leaderboard rank
            says "Not ranked" rather than a number (ui-playbook, 2026-08-17). */}
        {tierSummary.tier === 'Unranked' && (
          <Text style={[styles.unrankedHint, { color: colors.muted }]}>
            {t('analytics.tier_unranked_hint', {
              defaultValue:
                'Not ranked yet — add items from catalogued sets to build a rarity and completeness score.',
            })}
          </Text>
        )}

        <AnimatedPressable
          style={[styles.whyScoresBtn, { borderTopColor: colors.border }]}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); setScoreSheetVisible(true); }}
          accessibilityRole="button"
          accessibilityLabel={t('analytics.a11y_how_scores', { defaultValue: 'How are scores calculated?' })}
        >
          <Ionicons name="help-circle-outline" size={16} color={colors.accent} />
          <Text style={[styles.whyScoresText, { color: colors.brand.dark }]}>{t('analytics.how_scores_calculated', { defaultValue: 'How are these scores calculated?' })}</Text>
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
    borderRadius: radius.md,
    borderWidth: 1,
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
  },
  scoreLabel: {
    fontSize: text.sm,
    marginTop: 2,
  },
  scoreDivider: {
    width: 1,
    height: 32,
  },
  coverageLine: {
    fontSize: text.sm,
    marginTop: 12,
    textAlign: 'center',
  },
  unrankedHint: {
    fontSize: text.sm,
    marginTop: 8,
    textAlign: 'center',
    lineHeight: 18,
  },
  whyScoresBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
  },
  whyScoresText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
});
