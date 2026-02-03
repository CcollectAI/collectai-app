/**
 * useProgressRing Hook
 * Animated circular progress with accessibility support.
 */

import { useRef, useCallback, useMemo } from 'react';
import { Animated } from 'react-native';
import { useAnimationDuration } from '../lib/accessibility';
import { DURATION } from '../motion/tokens';

export type UseProgressRingOptions = {
  /** Initial progress value (0-1) */
  initialProgress?: number;
  /** Animation duration override */
  duration?: number;
};

export type UseProgressRingReturn = {
  /** Animated progress value (0-1) */
  animatedProgress: Animated.Value;
  /** Calculated stroke dash offset for SVG */
  strokeDashoffset: Animated.AnimatedInterpolation<number>;
  /** Set progress with animation */
  setProgress: (value: number) => void;
  /** Set progress instantly without animation */
  setProgressInstant: (value: number) => void;
};

/**
 * Hook for animated circular progress indicator.
 * @param circumference - The circumference of the progress ring SVG
 * @param options - Configuration options
 */
export function useProgressRing(
  circumference: number,
  options: UseProgressRingOptions = {}
): UseProgressRingReturn {
  const { initialProgress = 0, duration = DURATION.normal } = options;

  const animatedDuration = useAnimationDuration(duration);
  const animatedProgress = useRef(new Animated.Value(initialProgress)).current;

  const strokeDashoffset = useMemo(
    () =>
      animatedProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [circumference, 0],
        extrapolate: 'clamp',
      }),
    [animatedProgress, circumference]
  );

  const setProgress = useCallback(
    (value: number) => {
      const clampedValue = Math.max(0, Math.min(1, value));

      if (animatedDuration === 0) {
        // Instant when reduce motion is enabled
        animatedProgress.setValue(clampedValue);
      } else {
        Animated.timing(animatedProgress, {
          toValue: clampedValue,
          duration: animatedDuration,
          useNativeDriver: false,
        }).start();
      }
    },
    [animatedProgress, animatedDuration]
  );

  const setProgressInstant = useCallback(
    (value: number) => {
      const clampedValue = Math.max(0, Math.min(1, value));
      animatedProgress.setValue(clampedValue);
    },
    [animatedProgress]
  );

  return {
    animatedProgress,
    strokeDashoffset,
    setProgress,
    setProgressInstant,
  };
}
