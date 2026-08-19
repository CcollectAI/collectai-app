/**
 * Reusable Button component with consistent styling.
 * Variants: primary, secondary, ghost, danger.
 */

import React from 'react';
import { Text, StyleSheet, ViewStyle, TextStyle, ActivityIndicator } from 'react-native';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { Ionicons } from '@expo/vector-icons';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: keyof typeof Ionicons.glyphMap;
  iconPosition?: 'left' | 'right';
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  accessibilityLabel?: string;
  haptic?: boolean;
}

const SIZE_CONFIG = {
  sm: { paddingVertical: 8, paddingHorizontal: 14, fontSize: 13, iconSize: 14, borderRadius: 10 },
  md: { paddingVertical: 12, paddingHorizontal: 18, fontSize: 15, iconSize: 16, borderRadius: 12 },
  lg: { paddingVertical: 14, paddingHorizontal: 22, fontSize: 16, iconSize: 18, borderRadius: 14 },
} as const;

export const Button = React.memo(function Button({
  title,
  onPress,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  disabled = false,
  loading = false,
  fullWidth = false,
  style,
  textStyle,
  accessibilityLabel,
  haptic = true,
}: ButtonProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const sizeConfig = SIZE_CONFIG[size];

  const getVariantStyles = (): { container: ViewStyle; text: TextStyle; iconColor: string } => {
    switch (variant) {
      case 'primary':
        return {
          container: { backgroundColor: colors.accent },
          text: { color: colors.accentText, fontWeight: '600' },
          iconColor: colors.accentText,
        };
      case 'secondary':
        return {
          container: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.border },
          text: { color: colors.text, fontWeight: '600' },
          iconColor: colors.text,
        };
      case 'ghost':
        return {
          container: { backgroundColor: 'transparent' },
          text: { color: colors.accent, fontWeight: '600' },
          iconColor: colors.accent,
        };
      case 'danger':
        // ⚠️ DELIBERATELY hardcoded, and NOT a case for `accentText`.
        // `danger` is red in all four palettes (#EF4444 / #CC0000 / #FF4444),
        // so white always has contrast on it — while `accentText` is #000000
        // in high-contrast dark, which would put BLACK ON RED and make this
        // worse. The playbook's rule is about a fill that INVERTS with the
        // palette; this one does not. Checked 2026-08-19 during the branding
        // sweep; leave it.
        return {
          container: { backgroundColor: colors.danger },
          text: { color: '#FFFFFF', fontWeight: '600' },
          iconColor: '#FFFFFF',
        };
    }
  };

  const variantStyles = getVariantStyles();

  const handlePress = () => {
    if (disabled || loading) return;
    if (haptic) fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    onPress();
  };

  return (
    <AnimatedPressable
      onPress={handlePress}
      disabled={disabled || loading}
      style={[
        styles.base,
        {
          paddingVertical: sizeConfig.paddingVertical,
          paddingHorizontal: sizeConfig.paddingHorizontal,
          borderRadius: sizeConfig.borderRadius,
          opacity: disabled ? 0.5 : 1,
        },
        variantStyles.container,
        fullWidth && styles.fullWidth,
        style,
      ]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel || title}
      accessibilityState={{ disabled: disabled || loading }}
    >
      {loading ? (
        <ActivityIndicator size="small" color={variantStyles.iconColor} />
      ) : (
        <>
          {icon && iconPosition === 'left' && (
            <Ionicons name={icon} size={sizeConfig.iconSize} color={variantStyles.iconColor} />
          )}
          <Text style={[
            styles.text,
            { fontSize: sizeConfig.fontSize },
            variantStyles.text,
            textStyle,
          ]}>
            {title}
          </Text>
          {icon && iconPosition === 'right' && (
            <Ionicons name={icon} size={sizeConfig.iconSize} color={variantStyles.iconColor} />
          )}
        </>
      )}
    </AnimatedPressable>
  );
});

const styles = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  fullWidth: {
    width: '100%',
  },
  text: {
    textAlign: 'center',
  },
});

export default Button;
