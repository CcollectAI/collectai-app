/**
 * ConditionGradeSection — displays AI-estimated condition grade,
 * defect annotations, and grade reasoning on the scan result screen.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { DefectAnnotation, SuggestedGrade } from '@/data/types';

const TIFFANY_DARK = '#5FBFB6';

const SEVERITY_COLORS: Record<string, string> = {
  minor: '#22C55E',
  moderate: '#F59E0B',
  major: '#EF4444',
  severe: '#991B1B',
};

type Props = {
  defects: DefectAnnotation[];
  grade: SuggestedGrade | null;
};

export function ConditionGradeSection({ defects, grade }: Props) {
  const { colors } = useAppTheme();
  const [expanded, setExpanded] = useState(false);

  if (!grade && defects.length === 0) {
    return null;
  }

  const scaleLabel = grade?.scale?.toUpperCase() ?? 'GRADE';

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="shield-checkmark-outline" size={18} color={TIFFANY_DARK} />
        <Text style={[styles.title, { color: colors.text }]}>Condition Assessment</Text>
      </View>

      {/* Grade badge */}
      {grade && (
        <View style={styles.gradeRow}>
          <View style={[styles.gradeBadge, { borderColor: TIFFANY_DARK }]}>
            <Text style={[styles.gradeScale, { color: colors.muted }]}>{scaleLabel}</Text>
            <Text style={[styles.gradeValue, { color: colors.text }]}>{grade.gradeValue ?? 'N/A'}</Text>
          </View>
          <AnimatedPressable
            style={styles.reasoningBtn}
            onPress={() => setExpanded(!expanded)}
            accessibilityRole="button"
            accessibilityLabel="Toggle grade reasoning"
          >
            <Ionicons
              name={expanded ? 'chevron-up' : 'chevron-down'}
              size={16}
              color={colors.muted}
            />
            <Text style={[styles.reasoningBtnText, { color: colors.muted }]}>
              {expanded ? 'Hide reasoning' : 'Show reasoning'}
            </Text>
          </AnimatedPressable>
        </View>
      )}

      {/* Grade reasoning */}
      {expanded && grade?.reasoning && (
        <Text style={[styles.reasoning, { color: colors.muted }]}>{grade.reasoning}</Text>
      )}

      {/* Defect list */}
      {defects.length > 0 && (
        <View style={styles.defectList}>
          <Text style={[styles.subTitle, { color: colors.muted }]}>
            Detected Defects ({defects.length})
          </Text>
          {defects.map((defect, idx) => (
            <View key={idx} style={styles.defectRow}>
              <View
                style={[
                  styles.severityDot,
                  { backgroundColor: SEVERITY_COLORS[defect.severity] ?? '#888' },
                ]}
              />
              <View style={styles.defectInfo}>
                <Text style={[styles.defectType, { color: colors.text }]}>
                  {(defect.type ?? 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </Text>
                <Text style={[styles.defectDesc, { color: colors.muted }]} numberOfLines={1}>
                  {defect.location ?? 'Unknown location'} — {defect.description ?? ''}
                </Text>
              </View>
              <View
                style={[
                  styles.severityBadge,
                  { backgroundColor: (SEVERITY_COLORS[defect.severity] ?? '#888') + '15' },
                ]}
              >
                <Text
                  style={[
                    styles.severityText,
                    { color: SEVERITY_COLORS[defect.severity] ?? '#888' },
                  ]}
                >
                  {defect.severity}
                </Text>
              </View>
            </View>
          ))}
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
  gradeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  gradeBadge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gradeScale: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  gradeValue: {
    fontSize: 18,
    fontWeight: '800',
  },
  reasoningBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  reasoningBtnText: {
    fontSize: 12,
    fontWeight: '500',
  },
  reasoning: {
    fontSize: 13,
    lineHeight: 18,
    fontStyle: 'italic',
    marginBottom: 12,
  },
  subTitle: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  defectList: {
    marginTop: 4,
    gap: 6,
  },
  defectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  severityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  defectInfo: {
    flex: 1,
    gap: 2,
  },
  defectType: {
    fontSize: 13,
    fontWeight: '600',
  },
  defectDesc: {
    fontSize: 11,
    fontWeight: '400',
  },
  severityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  severityText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
});

export default ConditionGradeSection;
