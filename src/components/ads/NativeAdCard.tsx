/**
 * NativeAdCard Component
 *
 * In-feed native ad that blends with the item list.
 * Renders nothing when ads are disabled.
 *
 * When AppLovin is integrated, replace the inner View with
 * the real native ad template component.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAds } from '@/ads/useAds';
import { useAppTheme } from '@/hooks/useAppTheme';

interface NativeAdCardProps {
  /** Ad placement key */
  placement?: string;
  /** Optional style override */
  style?: object;
}

/**
 * Native ad card slot for list feeds. Returns null when ads are not active.
 */
export function NativeAdCard({ placement = 'items_native', style }: NativeAdCardProps) {
  const { showAds } = useAds();
  const { colors } = useAppTheme();

  if (!showAds) return null;

  // TODO: Replace with real AppLovin native ad template when SDK is integrated
  return (
    <View
      style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }, style]}
      accessibilityLabel="Sponsored content"
      accessibilityRole="none"
    >
      <Text style={[styles.label, { color: colors.muted }]}>Ad</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginHorizontal: 16,
    marginVertical: 6,
    minHeight: 80,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
});
