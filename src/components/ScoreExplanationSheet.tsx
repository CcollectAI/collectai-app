/**
 * ScoreExplanationSheet Component
 * Bottom sheet explaining Rarity, Completeness, and Diversity scores.
 * Styled to match PriceExplanationSheet.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

type ScoreExplanationSheetProps = {
  visible: boolean;
  onClose: () => void;
  rarityScore?: number;
  completenessScore?: number;
  diversificationScore?: number;
  tier?: string;
};

const TIFFANY = '#81D8D0';

const SCORE_SECTIONS = [
  {
    key: 'rarity',
    icon: 'sparkles-outline' as const,
    title: 'Rarity Score',
    description: 'Measures how rare and hard-to-find the items in your collection are.',
    factors: [
      'Limited edition and numbered items score higher',
      'Vaulted, retired, or discontinued items increase rarity',
      'Items with low print runs or production numbers',
      'Graded items (PSA/BGS/CGC) at high grades boost this score',
      'Regional exclusives and event-only releases',
    ],
  },
  {
    key: 'completeness',
    icon: 'checkmark-done-outline' as const,
    title: 'Completeness Score',
    description: 'Tracks how complete your sets and collections are across categories.',
    factors: [
      'Percentage of items owned within tracked sets',
      'Full sets and master sets score significantly higher',
      'Near-complete sets (>90%) receive a bonus multiplier',
      'Covering multiple sets within a category adds depth',
      'Key chase cards or anchor pieces weigh more heavily',
    ],
  },
  {
    key: 'diversity',
    icon: 'grid-outline' as const,
    title: 'Diversity Score',
    description: 'Reflects how well-diversified your collection is across different categories and types.',
    factors: [
      'Collecting across multiple categories improves this score',
      'Balanced allocation (not concentrated in one category) scores higher',
      'Covering different eras, series, or product lines within categories',
      'Mix of price tiers (entry-level through premium grails)',
      'Geographic and brand diversity adds to the score',
    ],
  },
];

function getScoreColor(score: number): string {
  if (score >= 0.75) return '#10B981';
  if (score >= 0.50) return '#F59E0B';
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
  const { colors } = useAppTheme();

  const scores: Record<string, number> = {
    rarity: rarityScore,
    completeness: completenessScore,
    diversity: diversificationScore,
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={[styles.header, { borderBottomColor: colors.border }]}>
          <Text style={[styles.headerTitle, { color: colors.text }]}>
            How Scores Work
          </Text>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              onClose();
            }}
            style={styles.closeButton}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons name="close" size={24} color={colors.text} />
          </AnimatedPressable>
        </View>

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
            const scoreColor = getScoreColor(score);
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
                  What counts:
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
              Scores update as you add, remove, or update items in your collection.
              They are calculated based on your catalog data and market reference information.
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  closeButton: {
    position: 'absolute',
    right: 16,
    padding: 4,
  },
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
