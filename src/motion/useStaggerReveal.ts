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

  // Ensure we have enough animated values.
  //
  // A VALUE CREATED AFTER THE FIRST REVEAL STARTS VISIBLE (2026-08-28).
  //
  // Found on the sim: the Items list showed a "LEGO" heading and a "Collection
  // total EUR 900" footer with a row-shaped BLANK between them. The row was
  // rendering — it was stranded at opacity 0. Relaunching the app fixed it,
  // which is what identified the cause: those items were added to the list
  // while the app was already open.
  //
  // The three lines that combine into it:
  //   1. new values were created at 0 whenever `enabled`,
  //   2. `reveal()` early-returns once `hasRevealed.current` is set, and
  //   3. the auto-start effect keys on `count > 0`, which does NOT change when
  //      the list grows from 8 items to 9.
  // So anything appended after the first reveal was created invisible and had
  // nothing left that would ever animate it up. Pull-to-refresh, pagination and
  // an optimistic add all reach it.
  //
  // Fixed HERE rather than by re-running the reveal, deliberately. Re-revealing
  // the tail is prettier, and its failure mode is a row that stays invisible —
  // the bug being fixed. This version's failure mode is a row that appears
  // without an animation. On a list of things a member owns, "unanimated" is a
  // cosmetic loss and "invisible" is the item looking sold, lost or deleted, so
  // the safe direction is not symmetric (`learning_silent_fallbacks_hide_dead_
  // features` — the construct that degrades to empty is the one that hides).
  if (opacities.current.length < animateCount) {
    // `startHidden` is evaluated per batch, not per hook: the FIRST batch is
    // what the stagger exists to animate.
    const startHidden = enabled && !hasRevealed.current;
    for (let i = opacities.current.length; i < animateCount; i++) {
      opacities.current.push(new Animated.Value(startHidden ? 0 : 1));
      translates.current.push(new Animated.Value(startHidden ? fromY : 0));
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
