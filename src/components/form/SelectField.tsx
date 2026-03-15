/**
 * SelectField -- Labeled dropdown/picker using ActionSheet (iOS) or Alert (Android).
 */

import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { radius, spacing, text as textTokens, fontWeight } from '@/theme/tokens';

export interface SelectOption {
  label: string;
  value: string;
}

export interface SelectFieldProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  error?: string | null;
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
}

export const SelectField = React.memo(function SelectField({
  label,
  value,
  options,
  onChange,
  error,
  disabled,
  placeholder = 'Select...',
  required,
}: SelectFieldProps) {
  const { colors } = useAppTheme();

  const selectedOption = options.find((o) => o.value === value);
  const displayText = selectedOption?.label ?? placeholder;

  const handlePress = useCallback(() => {
    if (disabled) return;
    showActionSheet(
      label,
      options.map((o) => o.label),
      (index) => {
        onChange(options[index].value);
      },
    );
  }, [label, options, onChange, disabled]);

  const borderColor = error ? colors.danger : colors.border;

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: colors.text }]}>
        {label}
        {required && <Text style={{ color: colors.accent }}> *</Text>}
      </Text>
      <Pressable
        onPress={handlePress}
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
        <Text
          style={[
            styles.triggerText,
            { color: selectedOption ? colors.text : colors.muted },
          ]}
          numberOfLines={1}
        >
          {displayText}
        </Text>
        <Ionicons name="chevron-down" size={16} color={colors.muted} />
      </Pressable>
      {error ? (
        <Text style={[styles.error, { color: colors.danger }]}>{error}</Text>
      ) : null}
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
    justifyContent: 'space-between',
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    height: 44,
  },
  triggerText: {
    fontSize: textTokens.md,
    flex: 1,
    marginRight: spacing.xs,
  },
  error: {
    fontSize: textTokens.sm,
    marginTop: spacing.xxs,
    marginLeft: spacing.xxs,
  },
});
