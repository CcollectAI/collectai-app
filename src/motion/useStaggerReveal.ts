/**
 * useStaggerReveal
 * Hook that provides staggered fade+slide-up animation for list items.
 * Each item animates with a small delay after the previous.
 *
 * Usage:
 *   const { getItemStyle, reveal } = useStaggerReveal(items.length);
 *   // In renderItem: <Animated.View style={getItemStyle(index)}>
 */

import { useRef, useCallback, useEffect } from 'react';
import { Animated } from 'react-native';
import { DURATION } from './tokens';

export interface StaggerRevealOptions {
  /** Number of items to animate */
  count: number;
  /** Delay between each item in ms. Default: 50 */
  staggerMs?: number;
  /** Duration of each item animation. Default: DURATION.normal (250) */
  duration?: number;
  /** Initial Y offset for slide-up. Default: 16 */
  fromY?: number;
  /** Max items to animate (rest appear instantly). Default: 10 */
  maxAnimated?: number;
  /** Whether to auto-start. Default: true */
  autoStart?: boolean;
  /** Whether animations are enabled (from settings). Default: true */
  enabled?: boolean;
}

export interface StaggerRevealResult {
  /** Get animated style for item at index */
  getItemStyle: (index: number) => {
    opacity: Animated.Value;
    transform: { translateY: Animated.Value }[];
  } | undefined;
  /** Manually trigger the stagger animation */
  reveal: () => void;
  /** Reset all animations */
  reset: () => void;
}

export function useStaggerReveal(options: StaggerRevealOptions): StaggerRevealResult {
  const {
    count,
    staggerMs = 50,
    duration = DURATION.normal,
    fromY = 16,
    maxAnimated = 10,
    autoStart = true,
    enabled = true,
  } = options;

  // Clamp to maxAnimated
  const animateCount = Math.min(count, maxAnimated);

  // Create stable arrays of Animated.Values
  const opacities = useRef<Animated.Value[]>([]);
  const translates = useRef<Animated.Value[]>([]);
  const hasRevealed = useRef(false);

  // Ensure we have enough animated values
  if (opacities.current.length < animateCount) {
    for (let i = opacities.current.length; i < animateCount; i++) {
      opacities.current.push(new Animated.Value(enabled ? 0 : 1));
      translates.current.push(new Animated.Value(enabled ? fromY : 0));
    }
  }

  const reveal = useCallback(() => {
    if (!enabled || hasRevealed.current) return;
    hasRevealed.current = true;

    const animations = [];
    for (let i = 0; i < animateCount; i++) {
      const delay = i * staggerMs;
      animations.push(
        Animated.parallel([
          Animated.timing(opacities.current[i], {
            toValue: 1,
            duration,
            delay,
            useNativeDriver: true,
          }),
          Animated.timing(translates.current[i], {
            toValue: 0,
            duration,
            delay,
            useNativeDriver: true,
          }),
        ]),
      );
    }

    Animated.parallel(animations).start();
  }, [animateCount, staggerMs, duration, enabled]);

  const reset = useCallback(() => {
    hasRevealed.current = false;
    for (let i = 0; i < opacities.current.length; i++) {
      opacities.current[i].setValue(enabled ? 0 : 1);
      translates.current[i].setValue(enabled ? fromY : 0);
    }
  }, [enabled, fromY]);

  useEffect(() => {
    if (autoStart && count > 0) {
      reveal();
    }
  }, [autoStart, count > 0]);

  const getItemStyle = useCallback(
    (index: number) => {
      if (!enabled || index >= animateCount) return undefined;
      return {
        opacity: opacities.current[index],
        transform: [{ translateY: translates.current[index] }],
      };
    },
    [enabled, animateCount],
  );

  return { getItemStyle, reveal, reset };
}
