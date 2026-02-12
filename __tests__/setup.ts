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
