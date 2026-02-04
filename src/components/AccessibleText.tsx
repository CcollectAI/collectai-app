/**
 * AccessibleText Component
 * Text component that scales with accessibility settings.
 */

import React from 'react';
import { Text, TextProps, StyleSheet } from 'react-native';
import { useAccessibility } from '@/lib/accessibilityContext';
import { fontSizes, getScaledFontSizes, FontSizeKey } from '@/theme/fontSizes';

export type AccessibleTextProps = TextProps & {
  /** Font size key from theme */
  size?: FontSizeKey;
  /** Text color */
  color?: string;
  /** Font weight */
  weight?: 'normal' | '500' | '600' | '700' | 'bold';
};

export function AccessibleText({
  size = 'medium',
  color,
  weight,
  style,
  children,
  ...props
}: AccessibleTextProps) {
  const { settings } = useAccessibility();
  const scaledSizes = getScaledFontSizes(settings.largeTextEnabled);

  const textStyle = [
    { fontSize: scaledSizes[size] },
    color && { color },
    weight && { fontWeight: weight },
    style,
  ];

  return (
    <Text
      style={textStyle}
      accessible
      {...props}
    >
      {children}
    </Text>
  );
}

export default AccessibleText;
