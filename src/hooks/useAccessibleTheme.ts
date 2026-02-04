/**
 * useAccessibleTheme Hook
 * Returns theme colors with high contrast support.
 */

import { useMemo } from 'react';
import { useColorMode, AppTheme } from '@/theme/colors';
import { useHighContrast } from '@/lib/accessibilityContext';
import { highContrastLight, highContrastDark } from '@/theme/highContrast';

// Import standard themes from colors.ts
const lightTheme: AppTheme = {
  background: '#e6f7fb',
  card: '#ffffff',
  border: '#d0e7f3',
  text: '#102a43',
  mutedText: 'rgba(15, 23, 42, 0.7)',
  accent: '#1fb6ff',
  accentText: '#ffffff',
  inputBackground: '#f8fbfd',
  inputBorder: '#c4d7e3',
};

const darkTheme: AppTheme = {
  background: '#06111a',
  card: '#0f2433',
  border: '#17354a',
  text: '#e3f3ff',
  mutedText: 'rgba(226, 232, 240, 0.7)',
  accent: '#38bdf8',
  accentText: '#0b1120',
  inputBackground: '#0b1b28',
  inputBorder: '#1e3a4c',
};

/**
 * Hook that returns the appropriate theme based on color mode and high contrast setting.
 */
export function useAccessibleTheme(): AppTheme {
  const { mode } = useColorMode();
  const highContrast = useHighContrast();

  return useMemo(() => {
    if (highContrast) {
      return mode === 'dark' ? highContrastDark : highContrastLight;
    }
    return mode === 'dark' ? darkTheme : lightTheme;
  }, [mode, highContrast]);
}
