/**
 * DateField -- Labeled date input with modal date picker.
 * Displays formatted date text, tappable to open a date picker modal.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Modal,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, spacing, text as textTokens, fontWeight, shadow } from '@/theme/tokens';

export interface DateFieldProps {
  label: string;
  value: Date | null;
  onChange: (date: Date) => void;
  minimumDate?: Date;
  maximumDate?: Date;
  error?: string | null;
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
}

function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export const DateField = React.memo(function DateField({
  label,
  value,
  onChange,
  minimumDate,
  maximumDate,
  error,
  disabled,
  placeholder = 'Select date...',
  required,
}: DateFieldProps) {
  const { colors } = useAppTheme();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [tempDate, setTempDate] = useState<Date>(value ?? new Date());

  const displayText = value ? formatDate(value) : placeholder;

  const handleOpen = useCallback(() => {
    if (disabled) return;
    setTempDate(value ?? new Date());
    setPickerVisible(true);
  }, [disabled, value]);

  const handleConfirm = useCallback(() => {
    onChange(tempDate);
    setPickerVisible(false);
  }, [tempDate, onChange]);

  const handleCancel = useCallback(() => {
    setPickerVisible(false);
  }, []);

  // Simple day navigation for the picker
  const adjustDay = useCallback(
    (delta: number) => {
      setTempDate((prev) => {
        const next = new Date(prev);
        next.setDate(next.getDate() + delta);
        if (minimumDate && next < minimumDate) return prev;
        if (maximumDate && next > maximumDate) return prev;
        return next;
      });
    },
    [minimumDate, maximumDate],
  );

  const borderColor = error ? colors.danger : colors.border;

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: colors.text }]}>
        {label}
        {required && <Text style={{ color: colors.accent }}> *</Text>}
      </Text>
      <Pressable
        onPress={handleOpen}
        disabled={disabled}
        style={[
          styles.trigger,
          {
            borderColor,
            backgroundColor: disabled ? colors.border + '40' : colors.background,
          },
        ]}
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${displayText}`}
      >
        <Ionicons
          name="calendar-outline"
          size={16}
          color={colors.muted}
          style={styles.icon}
        />
        <Text
          style={[
            styles.triggerText,
            { color: value ? colors.text : colors.muted },
          ]}
          numberOfLines={1}
        >
          {displayText}
        </Text>
      </Pressable>
      {error ? (
        <Text style={[styles.error, { color: colors.danger }]}>{error}</Text>
      ) : null}

      {/* Date picker modal */}
      <Modal
        visible={pickerVisible}
        transparent
        animationType="fade"
        onRequestClose={handleCancel}
      >
        <Pressable style={styles.overlay} onPress={handleCancel}>
          <Pressable
            style={[
              styles.pickerCard,
              {
                backgroundColor: colors.card,
                ...shadow.elevated,
              },
            ]}
            onPress={() => {}}
          >
            <Text style={[styles.pickerTitle, { color: colors.text }]}>
              {label}
            </Text>

            <View style={styles.pickerRow}>
              <Pressable
                onPress={() => adjustDay(-1)}
                style={[styles.arrowBtn, { backgroundColor: colors.background }]}
                accessibilityLabel="Previous day"
              >
                <Ionicons name="chevron-back" size={20} color={colors.text} />
              </Pressable>
              <Text style={[styles.dateDisplay, { color: colors.text }]}>
                {formatDate(tempDate)}
              </Text>
              <Pressable
                onPress={() => adjustDay(1)}
                style={[styles.arrowBtn, { backgroundColor: colors.background }]}
                accessibilityLabel="Next day"
              >
                <Ionicons name="chevron-forward" size={20} color={colors.text} />
              </Pressable>
            </View>

            <View style={styles.pickerActions}>
              <Pressable
                onPress={handleCancel}
                style={[styles.actionBtn, { borderColor: colors.border }]}
                accessibilityRole="button"
              >
                <Text style={[styles.actionBtnText, { color: colors.muted }]}>
                  Cancel
                </Text>
              </Pressable>
              <Pressable
                onPress={handleConfirm}
                style={[
                  styles.actionBtn,
                  { backgroundColor: colors.accent, borderColor: colors.accent },
                ]}
                accessibilityRole="button"
              >
                <Text style={[styles.actionBtnText, { color: colors.accentText }]}>
                  Confirm
                </Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: textTokens.sm,
    fontWeight: fontWeight.semibold,
    marginBottom: spacing.xs,
  },
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    height: 44,
  },
  icon: {
    marginRight: spacing.xs,
  },
  triggerText: {
    fontSize: textTokens.md,
    flex: 1,
  },
  error: {
    fontSize: textTokens.sm,
    marginTop: spacing.xxs,
    marginLeft: spacing.xxs,
  },

  /* Modal */
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  pickerCard: {
    width: 300,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: 'center',
  },
  pickerTitle: {
    fontSize: textTokens.lg,
    fontWeight: fontWeight.semibold,
    marginBottom: spacing.lg,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
  arrowBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dateDisplay: {
    fontSize: textTokens.xl,
    fontWeight: fontWeight.bold,
    minWidth: 140,
    textAlign: 'center',
  },
  pickerActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    width: '100%',
  },
  actionBtn: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    alignItems: 'center',
  },
  actionBtnText: {
    fontSize: textTokens.md,
    fontWeight: fontWeight.semibold,
  },
});
