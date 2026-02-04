/**
 * Font Size Tokens
 * Relative font sizes that scale with system text size.
 */

export const fontSizes = {
  /** Extra small: labels, captions */
  xs: 11,
  /** Small: secondary text, hints */
  small: 12,
  /** Medium: body text (default) */
  medium: 14,
  /** Large: emphasized body, subheadings */
  large: 16,
  /** Extra large: section headers */
  xl: 18,
  /** 2XL: screen titles */
  xxl: 22,
  /** 3XL: hero text */
  xxxl: 28,
} as const;

/**
 * Large text mode multiplier
 */
export const LARGE_TEXT_SCALE = 1.25;

/**
 * Get scaled font sizes for large text mode
 */
export function getScaledFontSizes(largeTextEnabled: boolean) {
  if (!largeTextEnabled) return fontSizes;

  const scale = LARGE_TEXT_SCALE;
  return {
    xs: Math.round(fontSizes.xs * scale),
    small: Math.round(fontSizes.small * scale),
    medium: Math.round(fontSizes.medium * scale),
    large: Math.round(fontSizes.large * scale),
    xl: Math.round(fontSizes.xl * scale),
    xxl: Math.round(fontSizes.xxl * scale),
    xxxl: Math.round(fontSizes.xxxl * scale),
  };
}

export type FontSizeKey = keyof typeof fontSizes;
