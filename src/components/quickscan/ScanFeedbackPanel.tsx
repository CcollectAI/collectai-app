/**
 * ScanFeedbackPanel — Inline correction UI for QuickScan results.
 * Allows users to tap name, category, or condition to correct the AI prediction.
 * Submits corrections to the feedback API for active learning.
 */

import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TextInput, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { featureFlags } from '@/config/featureFlags';
import { submitScanFeedback } from '@/api/collectorsApi';

type EditableField = 'name' | 'category' | 'condition';

type Props = {
  /** Name identified by the AI */
  name: string;
  /** Category identified by the AI */
  category: string;
  /** Condition guess from the AI (may be undefined) */
  conditionGuess?: string | null;
  /** Scan session ID needed to submit feedback */
  scanSessionId?: string | null;
  /** Whether FEATURE_SCAN_FEEDBACK is enabled */
  feedbackEnabled: boolean;
  /** Called when user taps on the name (when feedback is disabled) */
  onPressName?: () => void;
};

function ScanFeedbackPanelInner({
  name,
  category,
  conditionGuess,
  scanSessionId,
  feedbackEnabled,
  onPressName,
}: Props) {
  const { colors } = useAppTheme();

  const [editingField, setEditingField] = useState<EditableField | null>(null);
  const [editValue, setEditValue] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);

  const handleStartEdit = useCallback(
    (field: EditableField, current: string) => {
      if (!feedbackEnabled || !scanSessionId) return;
      setEditingField(field);
      setEditValue(current);
    },
    [feedbackEnabled, scanSessionId],
  );

  const handleSubmitFeedback = useCallback(async () => {
    if (!editingField || !scanSessionId) return;
    try {
      const feedback: {
        scanSessionId: string;
        correctedName?: string;
        correctedCategory?: string;
        correctedCondition?: string;
      } = { scanSessionId };
      if (editingField === 'name') feedback.correctedName = editValue;
      else if (editingField === 'category') feedback.correctedCategory = editValue;
      else if (editingField === 'condition') feedback.correctedCondition = editValue;
      await submitScanFeedback(feedback);
      setFeedbackSent(true);
      setEditingField(null);
      Alert.alert('Thanks!', 'Your correction helps improve future scans.');
    } catch {
      Alert.alert('Error', 'Could not submit feedback. Please try again.');
    }
  }, [editingField, editValue, scanSessionId]);

  const renderEditRow = (
    field: EditableField,
    iconSize: number,
    labelPrefix: string,
  ) => (
    <View style={styles.feedbackEditRow}>
      <TextInput
        style={[
          styles.feedbackInput,
          field !== 'name' && styles.feedbackInputSmall,
          { color: colors.text, borderColor: colors.brand.base },
        ]}
        value={editValue}
        onChangeText={setEditValue}
        autoFocus
        returnKeyType="done"
        onSubmitEditing={handleSubmitFeedback}
        accessibilityLabel={`Edit ${labelPrefix} value`}
      />
      <AnimatedPressable
        onPress={handleSubmitFeedback}
        style={[styles.feedbackSubmitBtn, { backgroundColor: colors.brand.base }]}
        accessibilityRole="button"
        accessibilityLabel={`Submit ${labelPrefix} correction`}
      >
        <Ionicons name="checkmark" size={iconSize} color="#FFF" />
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => setEditingField(null)}
        style={styles.feedbackCancelBtn}
        accessibilityRole="button"
        accessibilityLabel="Cancel editing"
      >
        <Ionicons name="close" size={iconSize} color={colors.muted} />
      </AnimatedPressable>
    </View>
  );

  const formatCategory = (cat: string) =>
    cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <View style={[styles.idCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      {/* Name */}
      {editingField === 'name' ? (
        renderEditRow('name', 16, 'item name')
      ) : (
        <AnimatedPressable
          onPress={() => {
            if (feedbackEnabled) {
              handleStartEdit('name', name);
            } else {
              onPressName?.();
            }
          }}
          accessibilityRole="button"
          accessibilityLabel={`Item name: ${name || 'Unknown Item'}. ${feedbackEnabled ? 'Tap to correct' : ''}`}
          accessibilityHint={feedbackEnabled ? 'Tap to correct' : undefined}
        >
          <Text style={[styles.idName, { color: colors.text }]} numberOfLines={3}>
            {name || 'Unknown Item'}
          </Text>
        </AnimatedPressable>
      )}

      {/* Category + Condition chips */}
      <View style={styles.idMeta}>
        {editingField === 'category' ? (
          renderEditRow('category', 14, 'category')
        ) : (
          <AnimatedPressable
            onPress={() => handleStartEdit('category', category)}
            accessibilityRole="button"
            accessibilityLabel={`Category: ${formatCategory(category)}`}
            style={[styles.categoryChip, { backgroundColor: colors.brand.base + '18' }]}
          >
            <Ionicons name="pricetag" size={12} color={colors.brand.dark} />
            <Text style={[styles.categoryChipText, { color: colors.brand.dark }]}>
              {formatCategory(category)}
            </Text>
            {feedbackEnabled && (
              <Ionicons name="pencil" size={10} color={colors.brand.dark} style={{ marginLeft: 4 }} />
            )}
          </AnimatedPressable>
        )}
        {!!conditionGuess && editingField !== 'condition' && (
          <AnimatedPressable
            onPress={() => handleStartEdit('condition', conditionGuess || '')}
            style={[styles.conditionChip, { backgroundColor: colors.border + '80' }]}
            accessibilityRole="button"
            accessibilityLabel={`Condition: ${conditionGuess?.replace(/_/g, ' ') ?? 'unknown'}`}
          >
            <Ionicons name="shield-checkmark" size={12} color={colors.muted} />
            <Text style={[styles.conditionChipText, { color: colors.text }]}>
              {conditionGuess
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (c) => c.toUpperCase())}
            </Text>
            {feedbackEnabled && (
              <Ionicons name="pencil" size={10} color={colors.muted} style={{ marginLeft: 4 }} />
            )}
          </AnimatedPressable>
        )}
        {editingField === 'condition' && renderEditRow('condition', 14, 'condition')}
      </View>

      {/* Feedback hint / sent badge */}
      {feedbackEnabled && !feedbackSent && scanSessionId && (
        <Text style={[styles.feedbackHint, { color: colors.muted }]}>
          Tap name, category, or condition to correct
        </Text>
      )}
      {feedbackSent && (
        <View style={styles.feedbackSentBadge}>
          <Ionicons name="checkmark-circle" size={14} color={colors.success} />
          <Text style={{ color: colors.success, fontSize: 11, marginLeft: 4 }}>
            Correction submitted
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  idCard: {
    marginTop: 12,
    marginHorizontal: 16,
    padding: 20,
    borderRadius: 20,
    borderWidth: 1,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  idName: {
    fontSize: 22,
    fontWeight: '800',
    lineHeight: 28,
    letterSpacing: -0.3,
  },
  idMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  categoryChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  conditionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  conditionChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  feedbackEditRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  feedbackInput: {
    flex: 1,
    borderWidth: 1.5,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 14,
    fontWeight: '600',
  },
  feedbackInputSmall: {
    fontSize: 12,
    paddingVertical: 4,
  },
  feedbackSubmitBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  feedbackCancelBtn: {
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  feedbackHint: {
    fontSize: 11,
    marginTop: 8,
    fontStyle: 'italic',
  },
  feedbackSentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
});

export const ScanFeedbackPanel = React.memo(ScanFeedbackPanelInner);
