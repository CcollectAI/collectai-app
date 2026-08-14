/**
 * Back chevron for a TAB screen.
 *
 * Tabs render their own headers (`(tabs)/_layout.tsx` sets
 * `headerShown: false`), so none of them inherited the native chevron, and the
 * two that use ScreenHeader suppressed it deliberately: a tab root has nothing
 * to pop.
 *
 * Added by request 2026-08-14. It is safe because `safeGoBack` never dead-ends
 * — with an empty stack it falls back to the Portfolio tab, which is a real
 * destination. The control always does something, which is the rule the
 * playbook cares about ("router.back() is a SILENT no-op").
 *
 * NOT used on the Portfolio tab itself. `safeGoBack` from there lands on
 * Portfolio, so the button would animate, fire a haptic and change nothing —
 * the dead-button failure this codebase has fixed twice. A control that does
 * nothing is worse than an absent one.
 */
import React from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { safeGoBack } from '@/lib/goBack';

export function TabBackButton({ color }: { color?: string } = {}) {
  const router = useRouter();
  const { colors } = useAppTheme();
  return (
    <AnimatedPressable
      onPress={() => safeGoBack(router)}
      style={styles.btn}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel="Go back"
    >
      <Ionicons name="chevron-back" size={24} color={color ?? colors.text} />
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  // Square and centred, matching the root header's button: an icon glyph's
  // advance width is narrower than its line height, so plain padding yields an
  // off-centre chevron.
  btn: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center', marginRight: 2 },
});
