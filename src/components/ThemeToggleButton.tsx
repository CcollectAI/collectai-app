/**
 * ThemeToggleButton — Global light/dark toggle icon.
 * Uses global settings via useAppTheme.
 */

import React from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

type Props = {
  /** Icon size, defaults to 22 */
  size?: number;
};

export const ThemeToggleButton: React.FC<Props> = ({ size = 22 }) => {
  const { isDark, toggleTheme, colors } = useAppTheme();

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        toggleTheme();
      }}
      style={styles.container}
      accessibilityRole="button"
      accessibilityLabel={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <Ionicons
        name={isDark ? 'sunny-outline' : 'moon-outline'}
        size={size}
        color={colors.text}
      />
    </AnimatedPressable>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: 4,
    marginLeft: 8,
  },
});

export default ThemeToggleButton;
