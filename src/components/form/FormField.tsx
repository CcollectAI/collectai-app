/**
 * FormField -- Reusable labeled text input with error display.
 * Uses design tokens for consistent styling across all forms.
 */

import React from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  type KeyboardTypeOptions,
  type ReturnKeyTypeOptions,
} from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, spacing, text as textTokens, fontWeight } from '@/theme/tokens';

export interface FormFieldProps {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  error?: string | null;
  multiline?: boolean;
  maxLength?: number;
  keyboardType?: KeyboardTypeOptions;
  returnKeyType?: ReturnKeyTypeOptions;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  disabled?: boolean;
  required?: boolean;
}

export const FormField = React.memo(function FormField({
  label,
  value,
  onChangeText,
  onBlur,
  placeholder,
  error,
  multiline,
  maxLength,
  keyboardType,
  returnKeyType,
  autoCapitalize,
  disabled,
  required,
}: FormFieldProps) {
  const { colors } = useAppTheme();

  const borderColor = error ? colors.danger : colors.border;

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: colors.text }]}>
        {label}
        {required && <Text style={{ color: colors.accent }}> *</Text>}
      </Text>
      <View
        style={[
          multiline ? styles.inputWrapMultiline : styles.inputWrap,
          {
            borderColor,
            backgroundColor: disabled ? colors.border + '40' : colors.background,
          },
        ]}
      >
        <TextInput
          value={value}
          onChangeText={onChangeText}
          onBlur={onBlur}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          style={[
            multiline ? styles.inputMultiline : styles.input,
            { color: colors.text },
          ]}
          multiline={multiline}
          maxLength={maxLength}
          keyboardType={keyboardType}
          returnKeyType={returnKeyType}
          autoCapitalize={autoCapitalize}
          editable={!disabled}
          textAlignVertical={multiline ? 'top' : 'center'}
          accessibilityLabel={label}
        />
      </View>
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
  inputWrap: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    height: 44,
    justifyContent: 'center',
  },
  inputWrapMultiline: {
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    minHeight: 100,
  },
  input: {
    fontSize: textTokens.md,
    paddingVertical: 0,
  },
  inputMultiline: {
    fontSize: textTokens.md,
    minHeight: 76,
  },
  error: {
    fontSize: textTokens.sm,
    marginTop: spacing.xxs,
    marginLeft: spacing.xxs,
  },
});
