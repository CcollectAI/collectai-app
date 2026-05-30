/**
 * GradientBackground — Full-screen gradient backdrop for auth screens.
 * Light: white → brand.lighter → white. Dark: slate-950 → teal-950 → slate-950.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useAppTheme } from '@/hooks/useAppTheme';

type Props = { children: React.ReactNode };

export function GradientBackground({ children }: Props) {
  const { colors, isDark } = useAppTheme();

  const gradientColors = isDark
    ? ['#020617', '#0A2A28', '#020617'] as const
    : ['#FFFFFF', colors.brand.lighter, '#FFFFFF'] as const;

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={gradientColors}
        locations={[0, 0.4, 1]}
        style={StyleSheet.absoluteFill}
      />
      {/* Decorative ambient circles — pointerEvents in STYLE (RN 0.81+).
          The legacy prop is deprecated and was getting silently ignored,
          letting these 300×300 circles overlap the Sign In + Continue with
          Apple buttons in the lower-left quadrant and swallow their taps. */}
      <View
        style={[
          styles.ambientCircle,
          styles.circleTopRight,
          { backgroundColor: colors.brand.base + '08', pointerEvents: 'none' },
        ]}
      />
      <View
        style={[
          styles.ambientCircle,
          styles.circleBottomLeft,
          { backgroundColor: colors.brand.base + '08', pointerEvents: 'none' },
        ]}
      />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  ambientCircle: {
    position: 'absolute',
    width: 300,
    height: 300,
    borderRadius: 150,
  },
  circleTopRight: {
    top: -80,
    right: -80,
  },
  circleBottomLeft: {
    bottom: -100,
    left: -100,
  },
});
