/**
 * LoadingButton — button that shows a spinner and disables itself during async operations.
 *
 * Usage:
 *   <LoadingButton
 *     title="Save Item"
 *     loadingTitle="Saving..."
 *     loading={isSaving}
 *     onPress={handleSave}
 *   />
 */

import React from 'react';
import {
  Pressable,
  Text,
  ActivityIndicator,
  StyleSheet,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

interface LoadingButtonProps {
  title: string;
  loadingTitle?: string;
  loading?: boolean;
  disabled?: boolean;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  style?: ViewStyle;
  textStyle?: TextStyle;
  accessibilityLabel?: string;
}

export function LoadingButton({
  title,
  loadingTitle,
  loading = false,
  disabled = false,
  onPress,
  variant = 'primary',
  style,
  textStyle,
  accessibilityLabel,
}: LoadingButtonProps) {
  const { colors, radius } = useAppTheme();
  const { settings } = useSettings();
  const isDisabled = loading || disabled;

  const bgColor =
    variant === 'danger' ? colors.danger :
    variant === 'secondary' ? 'transparent' :
    colors.accent;

  const borderColor = variant === 'secondary' ? colors.border : bgColor;

  const txtColor =
    variant === 'secondary' ? colors.text : '#FFFFFF';

  const handlePress = () => {
    if (isDisabled) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    onPress();
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? (loading ? (loadingTitle ?? title) : title)}
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      style={[
        styles.button,
        {
          backgroundColor: isDisabled ? colors.muted : bgColor,
          borderColor: isDisabled ? colors.muted : borderColor,
          borderRadius: radius.md,
          opacity: isDisabled ? 0.6 : 1,
        },
        style,
      ]}
    >
      {loading && (
        <ActivityIndicator
          size="small"
          color={txtColor}
          style={styles.spinner}
        />
      )}
      <Text style={[styles.text, { color: txtColor }, textStyle]}>
        {loading ? (loadingTitle ?? title) : title}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderWidth: 1,
    minHeight: 48,
  },
  spinner: {
    marginRight: 8,
  },
  text: {
    fontSize: 16,
    fontWeight: '600',
  },
});
