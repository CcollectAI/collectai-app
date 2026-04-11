/**
 * AdBanner Component
 *
 * Renders a banner ad placeholder. When ads are disabled (feature flag off,
 * paid user, or SDK not initialized), renders nothing.
 *
 * When the real AppLovin SDK is wired in, this component will render
 * the actual MaxAdView. For now it serves as the insertion point.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useAds } from '@/ads/useAds';
import type { BannerSize } from '@/ads/provider';

interface AdBannerProps {
  /** Ad placement key from AD_PLACEMENTS */
  placement: string;
  /** Banner size variant */
  size?: BannerSize;
  /** Optional style override */
  style?: object;
}

const BANNER_HEIGHTS: Record<BannerSize, number> = {
  standard: 50,
  large: 90,
  mrec: 250,
};

/**
 * Banner ad slot. Returns null when ads are not active.
 * Replace the inner View with the real SDK banner component
 * when AppLovin is integrated.
 */
export function AdBanner({ placement, size = 'standard', style }: AdBannerProps) {
  const { showAds } = useAds();

  if (!showAds) return null;

  const height = BANNER_HEIGHTS[size];

  // TODO: Replace with real AppLovin MaxAdView when SDK is integrated
  // <MaxAdView adUnitId={AD_PLACEMENTS[placement].unitId} adFormat="banner" style={{ height }} />
  return (
    <View
      style={[styles.container, { height }, style]}
      accessibilityLabel="Advertisement"
      accessibilityRole="none"
    />
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
});
