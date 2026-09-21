/**
 * ScoreExplanationSheet Component
 * Bottom sheet explaining Rarity, Completeness, and Diversity scores.
 * Styled to match PriceExplanationSheet.
 */

import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { BottomSheetModal } from './BottomSheetModal';
import { useTranslation } from 'react-i18next';

type ScoreExplanationSheetProps = {
  visible: boolean;
  onClose: () => void;
  rarityScore?: number;
  completenessScore?: number;
  diversificationScore?: number;
  tier?: string;
};

const TIFFANY = '#81D8D0';

/**
 * WHAT THESE SECTIONS MAY SAY.
 *
 * Every line here has to describe a rule the code actually applies. The
 * previous copy promised five rarity factors — print runs, PSA/BGS/CGC grades,
 * regional exclusives, "vaulted, retired or discontinued" — none of which any
 * scorer has ever read; completeness promised a ">90% bonus multiplier" and
 * "key chase cards weigh more heavily", and diversity promised eras, price
 * tiers and geography. The scores were 0 at the time, so the sheet explained
 * the derivation of a number that did not exist.
 *
 * The real rules: rarity is `_RARITY_TIERS` in server/app/ml/valuation_features.py
 * read off the catalogue row (or the item's own attributes), completeness is
 * owned ÷ `sets.total_items`, and diversity is 1 − Σ(category value share²).
 * Change one of those and change the line here in the same commit.
 */
const SCORE_SECTIONS = [
  {
    key: 'rarity',
    icon: 'sparkles-outline' as const,
    title: 'Rarity Score',
    description: 'The average rarity of the items we can identify in your collection.',
    factors: [
      'Read from the catalogue entry for each item, or from the details on the item itself',
      'Secret, hyper and one-of-one rares score highest, then ultra rare and alternate art',
      'Foils, holos and refractors sit above plain rares; commons score lowest',
      'Items we cannot identify a rarity for are left out of the average, not scored zero',
      'So this is an average over identified items — the card shows how many that is',
    ],
  },
  {
    key: 'completeness',
    icon: 'checkmark-done-outline' as const,
    title: 'Completeness Score',
    description: 'How much of each set you own, across the sets we hold a catalogue entry for.',
    factors: [
      'Items you own in a set, divided by the number of items that set contains',
      'Weighted by set size, so a finished large set counts for more than a finished small one',
      'A set we hold no catalogue entry for is skipped entirely',
      'Skipped, not counted as 0% — an unknown set size is not an empty set',
      'Name a set on your items to have it counted',
    ],
  },
  {
    key: 'diversity',
    icon: 'grid-outline' as const,
    title: 'Diversity Score',
    description: 'How evenly your collection\u2019s value is spread across categories.',
    factors: [
      'Measured on VALUE, not item count — one grail can outweigh fifty commons',
      'Everything in a single category scores near 0',
      'An even split across several categories scores near 100',
      'Adding a category moves this more than adding another item to one you already hold',
      'This is the only one of the three that never depends on catalogue data',
    ],
  },
];

function getScoreColor(score: number, successColor: string, warningColor: string): string {
  if (score >= 0.75) return successColor;
  if (score >= 0.50) return warningColor;
  return TIFFANY;
}

function getScoreLabel(score: number): string {
  if (score >= 0.85) return 'Excellent';
  if (score >= 0.70) return 'Strong';
  if (score >= 0.50) return 'Moderate';
  if (score >= 0.30) return 'Developing';
  return 'Getting started';
}

export function ScoreExplanationSheet({
  visible,
  onClose,
  rarityScore = 0,
  completenessScore = 0,
  diversificationScore = 0,
  tier,
}: ScoreExplanationSheetProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const handleClose = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    onClose();
  }, [onClose]);

  const scores: Record<string, number> = {
    rarity: rarityScore,
    completeness: completenessScore,
    diversity: diversificationScore,
  };

  return (
    <BottomSheetModal
      visible={visible}
      onClose={handleClose}
      title={t('guide.how_scores_work', { defaultValue: 'How Scores Work' })}
      colors={colors}
      mode="pageSheet"
    >
        <ScrollView
          style={styles.content}
          contentContainerStyle={styles.contentContainer}
          showsVerticalScrollIndicator={false}
        >
          {/* Summary */}
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="bulb-outline" size={20} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Overview</Text>
            </View>
            <Text style={[styles.summaryText, { color: colors.text }]}>
              Your portfolio tier ({tier ?? 'Unranked'}) is determined by three scores that evaluate different
              aspects of your collection. Each score ranges from 0 to 100.
            </Text>
          </View>

          {/* Score Sections */}
          {SCORE_SECTIONS.map((sec) => {
            const score = scores[sec.key] ?? 0;
            const displayScore = Math.round(score * 100);
            const scoreColor = getScoreColor(score, colors.success, colors.warning);
            const scoreLabel = getScoreLabel(score);

            return (
              <View
                key={sec.key}
                style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}
              >
                <View style={styles.sectionHeader}>
                  <Ionicons name={sec.icon} size={20} color={colors.accent} />
                  <Text style={[styles.sectionTitle, { color: colors.text }]}>{sec.title}</Text>
                </View>

                {/* Score badge */}
                <View style={styles.scoreBadgeRow}>
                  <View style={[styles.scoreBadge, { backgroundColor: scoreColor + '20' }]}>
                    <Text style={[styles.scoreBadgeValue, { color: scoreColor }]}>
                      {displayScore}
                    </Text>
                    <Text style={[styles.scoreBadgeMax, { color: colors.muted }]}>/100</Text>
                  </View>
                  <Text style={[styles.scoreLevelLabel, { color: scoreColor }]}>
                    {scoreLabel}
                  </Text>
                </View>

                {/* Progress bar */}
                <View style={[styles.progressBarBg, { backgroundColor: colors.border }]}>
                  <View
                    style={[
                      styles.progressBarFill,
                      { width: `${Math.min(displayScore, 100)}%`, backgroundColor: scoreColor },
                    ]}
                  />
                </View>

                <Text style={[styles.scoreDescription, { color: colors.text }]}>
                  {sec.description}
                </Text>

                {/* Key factors */}
                <Text style={[styles.factorsHeading, { color: colors.text }]}>
                  {t('guide.what_counts', { defaultValue: 'What counts:' })}
                </Text>
                {sec.factors.map((factor, index) => (
                  <View key={index} style={styles.factorRow}>
                    <View style={[styles.factorBullet, { backgroundColor: colors.accent }]} />
                    <Text style={[styles.factorText, { color: colors.text }]}>{factor}</Text>
                  </View>
                ))}
              </View>
            );
          })}

          {/* Disclaimer */}
          <View style={[styles.disclaimerSection, { backgroundColor: colors.background }]}>
            <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
            <Text style={[styles.disclaimerText, { color: colors.muted }]}>
              {t('guide.scores_update_note', { defaultValue: 'Scores update as you add, remove, or update items in your collection. They are calculated based on your catalog data and market reference information.' })}
            </Text>
          </View>
        </ScrollView>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
    gap: 16,
  },
  section: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  summaryText: {
    fontSize: 14,
    lineHeight: 21,
  },
  scoreBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 10,
  },
  scoreBadge: {
    flexDirection: 'row',
    alignItems: 'baseline',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 2,
  },
  scoreBadgeValue: {
    fontSize: 22,
    fontWeight: '800',
  },
  scoreBadgeMax: {
    fontSize: 13,
    fontWeight: '500',
  },
  scoreLevelLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  progressBarBg: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 12,
  },
  progressBarFill: {
    height: 6,
    borderRadius: 3,
  },
  scoreDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  factorsHeading: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  factorRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 6,
  },
  factorBullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 7,
  },
  factorText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 19,
  },
  disclaimerSection: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 12,
    borderRadius: 8,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 18,
  },
});

export default ScoreExplanationSheet;
