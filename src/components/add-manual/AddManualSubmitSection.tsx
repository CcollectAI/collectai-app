/**
 * AddManualSubmitSection — Submit button and tip footer.
 */

import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface AddManualSubmitSectionProps {
  canSubmit: boolean;
  isSaving: boolean;
  onSubmit: () => void;
}

export const AddManualSubmitSection = React.memo(function AddManualSubmitSection({
  canSubmit,
  isSaving,
  onSubmit,
}: AddManualSubmitSectionProps) {
  const { colors } = useAppTheme();

  return (
    <>
      <AnimatedPressable
        onPress={onSubmit}
        disabled={!canSubmit}
        style={[styles.submitButton, { backgroundColor: canSubmit ? colors.accent : colors.border }]}
        accessibilityRole="button"
        accessibilityLabel="Save to collection"
        accessibilityState={{ disabled: !canSubmit }}
        testID="save-button"
      >
        {isSaving ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : (
          <>
            <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
            <Text style={styles.submitButtonText}>Save to Collection</Text>
          </>
        )}
      </AnimatedPressable>

      <View style={styles.footerHint}>
        <Ionicons name="bulb-outline" size={14} color={colors.muted} />
        <Text style={[styles.footerHintText, { color: colors.muted }]}>
          Tip: Use QuickScan for faster entry with AI assistance
        </Text>
      </View>
    </>
  );
});

const styles = StyleSheet.create({
  submitButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 12, marginTop: 4,
  },
  submitButtonText: { fontSize: 15, fontWeight: '600', color: '#FFFFFF' },
  footerHint: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 16 },
  footerHintText: { fontSize: 12 },
});
