/**
 * Ads Module — barrel export
 */

export { getAdProvider, setAdProvider, resetAdProvider } from './provider';
export type { AdProvider, AdConfig, AdFormat, BannerSize, AdImpression } from './provider';
export { AD_PLACEMENTS, AD_THROTTLE } from './config';
export { useAds } from './useAds';
export { useInterstitial } from './useInterstitial';
