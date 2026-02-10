/**
 * Lightweight logger utility for CollectAI.
 *
 * - info/warn are gated behind __DEV__ so they are stripped in production builds.
 * - error always logs (production errors should still surface).
 * - The implementation wraps console.* so it can be swapped for a remote
 *   logging service (e.g. Sentry, Datadog) without touching call sites.
 */

const TAG = '[CollectAI]';

const logger = {
  info: (...args: unknown[]) => {
    if (__DEV__) console.log(TAG, ...args);
  },
  warn: (...args: unknown[]) => {
    if (__DEV__) console.warn(TAG, ...args);
  },
  error: (...args: unknown[]) => {
    console.error(TAG, ...args);
  },
};

export default logger;
