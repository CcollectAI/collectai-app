/**
 * BarcodeModeSelector — manual ISBN entry card shown below the camera viewfinder.
 */

import React from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useScannerTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

interface BarcodeModeSelectorProps {
  manualIsbn: string;
  onChangeIsbn: (value: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  hapticsEnabled: boolean;
}

export const BarcodeModeSelector = React.memo(function BarcodeModeSelector({
  manualIsbn,
  onChangeIsbn,
  onSubmit,
  isSubmitting,
  hapticsEnabled,
}: BarcodeModeSelectorProps) {
  const { colors } = useScannerTheme();

  return (
    <ScrollView
      style={styles.manualEntryScroll}
      contentContainerStyle={styles.manualEntryScrollContent}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={[styles.manualEntryCard, { backgroundColor: colors.card }]}>
        <Text style={[styles.manualEntryTitle, { color: colors.text }]}>
          Manual Entry
        </Text>
        <Text style={[styles.manualEntryHelper, { color: colors.muted }]}>
          Can't scan? Type the ISBN code from the back cover
        </Text>
        <View style={styles.manualEntryRow}>
          <TextInput
            style={[styles.manualInput, {
              backgroundColor: colors.background,
              borderColor: colors.border,
              color: colors.text,
            }]}
            placeholder="978-0-123456-78-9"
            placeholderTextColor={colors.muted}
            value={manualIsbn}
            onChangeText={onChangeIsbn}
            keyboardType="number-pad"
            maxLength={17}
            returnKeyType="search"
            onSubmitEditing={onSubmit}
            accessibilityLabel="ISBN input field"
            accessibilityHint="Enter 10 or 13 digit ISBN number"
          />
          <AnimatedPressable
            style={[styles.manualSubmitButton, {
              backgroundColor: colors.accent,
              opacity: manualIsbn.length < 10 || isSubmitting ? 0.5 : 1,
            }]}
            onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: hapticsEnabled }); onSubmit(); }}
            disabled={manualIsbn.length < 10 || isSubmitting}
            accessibilityLabel="Look up ISBN"
            accessibilityRole="button"
          >
            {isSubmitting ? (
              <ActivityIndicator size="small" color={colors.card} />
            ) : (
              <>
                <Ionicons name="search" size={18} color={colors.card} />
                <Text style={[styles.primaryButtonText, { color: colors.card }]}>Look Up</Text>
              </>
            )}
          </AnimatedPressable>
        </View>
      </View>
    </ScrollView>
  );
});

const styles = StyleSheet.create({
  manualEntryScroll: {
    maxHeight: 200,
    marginTop: 4,
  },
  manualEntryScrollContent: {
    flexGrow: 1,
  },
  manualEntryCard: {
    margin: 16,
    marginTop: 12,
    padding: 20,
    borderRadius: 16,
  },
  manualEntryTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 6,
  },
  manualEntryHelper: {
    fontSize: 13,
    marginBottom: 16,
    lineHeight: 18,
  },
  manualEntryRow: {
    flexDirection: 'row',
    gap: 10,
  },
  manualInput: {
    flex: 1,
    height: 52,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 16,
    fontSize: 17,
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  manualSubmitButton: {
    flexDirection: 'row',
    height: 50,
    paddingHorizontal: 16,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
});
