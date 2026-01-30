/**
 * Motion Tokens
 * Centralized timing and easing constants for consistent animations.
 */

export const DURATION = {
  instant: 100,
  fast: 150,
  normal: 250,
  slow: 400,
  reveal: 300,
} as const;

export const EASING = {
  // Standard material-style easings
  standard: [0.4, 0.0, 0.2, 1] as const,
  decelerate: [0.0, 0.0, 0.2, 1] as const,
  accelerate: [0.4, 0.0, 1, 1] as const,
  // Spring-like bounce
  bounce: [0.68, -0.55, 0.265, 1.55] as const,
} as const;

export const SCALE = {
  pressed: 0.97,
  hover: 1.02,
} as const;

export type DurationKey = keyof typeof DURATION;
export type EasingKey = keyof typeof EASING;
