/**
 * AccessiblePressable Component
 * Pressable with built-in accessibility support.
 */

import React from 'react';
import { Pressable, PressableProps, ViewStyle, StyleProp } from 'react-native';

export type AccessiblePressableProps = PressableProps & {
  /** Accessible label describing the button */
  accessibilityLabel: string;
  /** Hint describing what happens when pressed */
  accessibilityHint?: string;
  /** Override the default 'button' role */
  accessibilityRole?: PressableProps['accessibilityRole'];
};

/**
 * Pressable component with required accessibility props.
 * Ensures all interactive elements have proper labels.
 */
export function AccessiblePressable({
  accessibilityLabel,
  accessibilityHint,
  accessibilityRole = 'button',
  disabled,
  children,
  ...props
}: AccessiblePressableProps) {
  return (
    <Pressable
      accessible
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      accessibilityRole={accessibilityRole}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      {...props}
    >
      {children}
    </Pressable>
  );
}

export default AccessiblePressable;
