/**
 * Jest setup file for React Native Testing Library.
 *
 * - Imports built-in RNTL v13 jest matchers (toBeOnTheScreen, toHaveTextContent, etc.)
 * - Sets global __DEV__ flag for modules that depend on it
 */

// Register RNTL built-in matchers with Jest's expect
require('@testing-library/react-native/build/matchers/extend-expect');

// Provide a global __DEV__ flag (used by src/utils/logger.ts and others)
// @ts-expect-error -- __DEV__ is a React Native global, not defined in Node
globalThis.__DEV__ = true;

// Mock react-i18next globally so components using useTranslation() render English
// strings in snapshot/unit tests without needing to initialize i18next per-test.
jest.mock('react-i18next', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const en = require('../src/i18n/locales/en.json');
  const resolve = (key: string): unknown => {
    const parts = key.split('.');
    let cur: unknown = en;
    for (const p of parts) {
      if (cur && typeof cur === 'object' && p in (cur as Record<string, unknown>)) {
        cur = (cur as Record<string, unknown>)[p];
      } else {
        return undefined;
      }
    }
    return cur;
  };
  const t = (key: string, vars?: Record<string, unknown>): string => {
    const val = resolve(key);
    if (typeof val !== 'string') return key;
    if (!vars) return val;
    return val.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : ''));
  };
  return {
    useTranslation: () => ({ t, i18n: { language: 'en', changeLanguage: jest.fn() } }),
    initReactI18next: { type: '3rdParty', init: jest.fn() },
    Trans: ({ children }: { children: React.ReactNode }) => children,
  };
});

// AsyncStorage has a native module; without this mock any test that
// transitively imports it throws at import time.
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);
