/**
 * CategoryGradingGuide — shows the relevant grading standards for a category.
 * Static data component: maps categories to their grading services/scales.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

type GradingStandard = {
  service: string;
  scale: string;
  grades: string[];
  tip: string;
};

const GRADING_MAP: Record<string, GradingStandard[]> = {
  pokemon: [
    { service: 'PSA', scale: '1-10', grades: ['10 Gem Mint', '9 Mint', '8 NM-MT', '7 NM'], tip: 'PSA 10 carries a 5-10x premium over raw' },
    { service: 'CGC', scale: '1-10', grades: ['10 Pristine', '9.5 Gem Mint', '9 Mint', '8.5 NM-MT+'], tip: 'CGC sub-grades (centering, edges, corners, surface) add transparency' },
    { service: 'BGS', scale: '1-10', grades: ['10 Black Label', '9.5 Gem Mint', '9 Mint'], tip: 'BGS Black Label 10 is the rarest and most valuable' },
  ],
  mtg: [
    { service: 'PSA', scale: '1-10', grades: ['10 Gem Mint', '9 Mint', '8 NM-MT'], tip: 'Alpha/Beta cards benefit most from grading' },
    { service: 'CGC', scale: '1-10', grades: ['10 Pristine', '9.5 Gem Mint', '9 Mint'], tip: 'CGC is gaining popularity for MTG grading' },
    { service: 'BGS', scale: '1-10', grades: ['10 Black Label', '9.5 Gem Mint'], tip: 'BGS quad 9.5+ commands significant premiums' },
  ],
  sportscards: [
    { service: 'PSA', scale: '1-10', grades: ['10 Gem Mint', '9 Mint', '8 NM-MT'], tip: 'PSA dominates sports card grading market' },
    { service: 'BGS', scale: '1-10', grades: ['10 Pristine', '9.5 Gem Mint', '9 Mint'], tip: 'BGS 9.5 with all 9.5+ sub-grades is highly sought' },
    { service: 'SGC', scale: '1-10', grades: ['10 Gem Mint', '9.5 Mint+', '9 Mint'], tip: 'SGC is popular for vintage cards pre-1980' },
  ],
  comic_books: [
    { service: 'CGC', scale: '0.5-10', grades: ['10.0 Gem Mint', '9.8 NM/M', '9.6 NM+', '9.4 NM'], tip: 'CGC 9.8 is the most commonly targeted grade for modern comics' },
    { service: 'CBCS', scale: '0.5-10', grades: ['10.0 Gem Mint', '9.8 NM/M', '9.6 NM+'], tip: 'CBCS verified signatures add collector value' },
  ],
  funko: [
    { service: 'AFA', scale: 'U/C/B grading', grades: ['U95', 'U90', 'U85', 'U80'], tip: 'AFA grades the figure AND the box separately' },
  ],
  manga: [
    { service: 'CGC', scale: '0.5-10', grades: ['9.8 NM/M', '9.6 NM+', '9.4 NM'], tip: 'First print editions in 9.6+ command top premiums' },
  ],
  vinyl_records: [
    { service: 'Goldmine', scale: 'M to P', grades: ['M (Mint)', 'NM (Near Mint)', 'VG+ (Very Good Plus)', 'VG', 'G+'], tip: 'Goldmine standard rates record AND sleeve separately' },
  ],
  sneakers: [
    { service: 'CheckCheck', scale: 'Pass/Fail', grades: ['Pass', 'Fail'], tip: 'Authentication focuses on legitimacy, not condition grading' },
    { service: 'Tradeblock', scale: 'DS/VNDS/Good/Beaters', grades: ['DS (Deadstock)', 'VNDS (Very Near DS)', 'Good', 'Beaters'], tip: 'DS (deadstock, never worn) commands the highest prices' },
  ],
  watches: [
    { service: 'Condition', scale: 'NOS to Poor', grades: ['NOS (New Old Stock)', 'Excellent', 'Very Good', 'Good', 'Fair'], tip: 'Full box+papers (complete set) adds 15-30% to value' },
  ],
  coins: [
    { service: 'PCGS', scale: '1-70 Sheldon', grades: ['MS-70 Perfect', 'MS-69 Near Perfect', 'MS-67 Superb Gem', 'MS-65 Gem'], tip: 'PCGS and NGC are the two most trusted coin grading services' },
    { service: 'NGC', scale: '1-70 Sheldon', grades: ['MS-70', 'MS-69', 'MS-68', 'MS-67'], tip: 'NGC Star designation recognizes exceptional eye appeal' },
  ],
  stamps: [
    { service: 'PSE', scale: '0-100', grades: ['100 (Gem)', '98 (Superb)', '95 (Extremely Fine)'], tip: 'PSE is the dominant grading service for US stamps' },
  ],
};

// Aliases — many categories share grading systems
const ALIASES: Record<string, string> = {
  lorcana: 'pokemon', yugioh: 'pokemon', digimon: 'pokemon', one_piece_tcg: 'pokemon',
  baseball_cards: 'sportscards', basketball_cards: 'sportscards', football_cards: 'sportscards',
  hot_toys: 'funko', // AFA also grades action figures
  action_figures: 'funko',
};

type Props = { categoryId: string };

export default React.memo(function CategoryGradingGuide({ categoryId }: Props) {
  const { colors } = useAppTheme();
  const [expanded, setExpanded] = useState(false);

  const key = ALIASES[categoryId] ?? categoryId;
  const standards = GRADING_MAP[key];
  if (!standards) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <AnimatedPressable
        style={styles.header}
        onPress={() => setExpanded(!expanded)}
        accessibilityRole="button"
        accessibilityLabel={`Grading standards, ${expanded ? 'collapse' : 'expand'}`}
      >
        <Ionicons name="shield-checkmark-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Grading Standards</Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.muted} />
      </AnimatedPressable>

      {expanded && standards.map((s) => (
        <View key={s.service} style={[styles.serviceBlock, { borderTopColor: colors.border }]}>
          <View style={styles.serviceHeader}>
            <Text style={[styles.serviceName, { color: colors.text }]}>{s.service}</Text>
            <Text style={[styles.serviceScale, { color: colors.muted }]}>{s.scale}</Text>
          </View>
          <View style={styles.grades}>
            {s.grades.map((g) => (
              <View key={g} style={[styles.gradePill, { backgroundColor: colors.accent + '18' }]}>
                <Text style={[styles.gradeText, { color: colors.accent }]}>{g}</Text>
              </View>
            ))}
          </View>
          <Text style={[styles.tip, { color: colors.muted }]}>
            <Ionicons name="bulb-outline" size={11} color={colors.muted} /> {s.tip}
          </Text>
        </View>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  container: { borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 16 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 16, fontWeight: '700', flex: 1 },
  serviceBlock: { borderTopWidth: StyleSheet.hairlineWidth, marginTop: 12, paddingTop: 12 },
  serviceHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  serviceName: { fontSize: 14, fontWeight: '700' },
  serviceScale: { fontSize: 12 },
  grades: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  gradePill: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  gradeText: { fontSize: 11, fontWeight: '600' },
  tip: { fontSize: 11, lineHeight: 16, fontStyle: 'italic' },
});
