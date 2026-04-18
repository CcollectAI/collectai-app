/** When true, hides non-core screens (events, build & paint, sell, gamification, sponsor, twitch) */
export const BETA_MODE = false;

export const featureFlags = {
  darkMode: false,
  FEATURE_HAPTICS_MICRO_ANIMATIONS: true,
  FEATURE_ACCESSIBILITY_ENHANCEMENTS: true,
  FEATURE_DATA_INSIGHTS_ALERTS: true,
  FEATURE_EXPLAINABLE_AI_INTERFACES: true,
  FEATURE_GESTURE_THUMB_NAVIGATION: true,
  FEATURE_ANALYTICS: true,
  // QuickScan enhancements
  FEATURE_QUICKSCAN_FAST_PATH: true,
  FEATURE_SCAN_FEEDBACK: true,
  FEATURE_SOCIAL_PROOF: true,
  FEATURE_DUPLICATE_DETECTION: true,
  FEATURE_CONDITION_GRADING: true,
  FEATURE_EDGE_CLASSIFICATION: true,
  FEATURE_VIEWFINDER_HINTS: true,
  FEATURE_MULTI_ITEM_SCAN: true,
  FEATURE_COMPARISON_SCAN: true,
  // Ads — dark by default. Enable via PostHog remote flag or manually
  // when user threshold is reached. Free users only; paid = ad-free.
  FEATURE_ADS: false,
};
