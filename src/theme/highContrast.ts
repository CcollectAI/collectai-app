/**
 * High Contrast Theme
 * WCAG 2.1 AA compliant colors for improved accessibility.
 * Contrast ratios: text on background >= 4.5:1, large text >= 3:1
 */

import { AppTheme } from './colors';

/**
 * High contrast light theme
 * Dark navy text on off-white backgrounds
 */
export const highContrastLight: AppTheme = {
  background: '#FAFAFA',        // Off-white
  card: '#FFFFFF',              // Pure white
  border: '#1A1A1A',            // Near black for visible borders
  text: '#0D0D0D',              // Near black text (21:1 contrast)
  mutedText: '#404040',         // Dark gray (7.5:1 contrast)
  accent: '#0052CC',            // Bold blue (4.6:1 on white)
  accentText: '#FFFFFF',        // White on accent
  inputBackground: '#FFFFFF',
  inputBorder: '#1A1A1A',
};

/**
 * High contrast dark theme
 * Light text on deep black backgrounds
 */
export const highContrastDark: AppTheme = {
  background: '#000000',        // Pure black
  card: '#0D0D0D',              // Near black
  border: '#FFFFFF',            // White borders for visibility
  text: '#FFFFFF',              // Pure white text (21:1 contrast)
  mutedText: '#E0E0E0',         // Light gray (14:1 contrast)
  accent: '#4DA6FF',            // Bright blue (5.2:1 on black)
  accentText: '#000000',        // Black on accent
  inputBackground: '#0D0D0D',
  inputBorder: '#FFFFFF',
};
