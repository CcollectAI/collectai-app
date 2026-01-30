/**
 * useEnterReveal
 * Hook that provides fade+slide-up animation for screen content.
 * Returns animated style to apply to container.
 */

import { useRef, useEffect } from 'react';
import { Animated } from 'react-native';
import { DURATION } from './tokens';

export interface EnterRevealOptions {
  /** Animation duration in ms. Default: DURATION.reveal (300ms) */
  duration?: number;
  /** Delay before animation starts in ms. Default: 0 */
  delay?: number;
  /** Initial Y offset for slide-up. Default: 20 */
  fromY?: number;
  /** Whether to auto-start animation on mount. Default: true */
  autoStart?: boolean;
}

export interface EnterRevealResult {
  /** Animated style to spread on your container */
  animatedStyle: {
    opacity: Animated.Value;
    transform: { translateY: Animated.Value }[];
  };
  /** Manually trigger the reveal animation */
  reveal: () => void;
  /** Reset animation to initial state */
  reset: () => void;
}

export function useEnterReveal(options: EnterRevealOptions = {}): EnterRevealResult {
  const {
    duration = DURATION.reveal,
    delay = 0,
    fromY = 20,
    autoStart = true,
  } = options;

  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(fromY)).current;

  const reveal = () => {
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration,
        delay,
        useNativeDriver: true,
      }),
      Animated.timing(translateY, {
        toValue: 0,
        duration,
        delay,
        useNativeDriver: true,
      }),
    ]).start();
  };

  const reset = () => {
    opacity.setValue(0);
    translateY.setValue(fromY);
  };

  useEffect(() => {
    if (autoStart) {
      reveal();
    }
  }, [autoStart]);

  return {
    animatedStyle: {
      opacity,
      transform: [{ translateY }],
    },
    reveal,
    reset,
  };
}
