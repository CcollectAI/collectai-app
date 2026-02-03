/**
 * Accessibility Utilities
 * Hooks for respecting user accessibility preferences.
 */

import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

/**
 * Hook to detect if the user has enabled "Reduce Motion" in system settings.
 */
export function useReduceMotion(): boolean {
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    // Get initial value
    AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);

    // Subscribe to changes
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReduceMotion
    );

    return () => {
      subscription.remove();
    };
  }, []);

  return reduceMotion;
}

/**
 * Returns an animation duration that respects reduce motion settings.
 * @param baseMs - The base duration in milliseconds
 * @returns 0 when reduce motion is enabled, otherwise baseMs
 */
export function useAnimationDuration(baseMs: number): number {
  const reduceMotion = useReduceMotion();
  return reduceMotion ? 0 : baseMs;
}
