/**
 * Simple logger utility that respects __DEV__ mode.
 * Logs are only printed in development mode to keep production clean.
 */

// React Native global __DEV__ declaration
declare const __DEV__: boolean | undefined;

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerOptions {
  prefix?: string;
  enabled?: boolean;
}

// Check for React Native's __DEV__ global, fallback to NODE_ENV check
const isDev = (() => {
  try {
    return typeof __DEV__ !== 'undefined' ? __DEV__ : process.env.NODE_ENV !== 'production';
  } catch {
    return true; // Default to dev mode if detection fails
  }
})();

function createLogger(options: LoggerOptions = {}) {
  const { prefix = '', enabled = isDev } = options;
  const formatPrefix = prefix ? `[${prefix}]` : '';

  return {
    debug: (...args: unknown[]) => {
      if (enabled) {
        console.log(formatPrefix, ...args);
      }
    },
    info: (...args: unknown[]) => {
      if (enabled) {
        console.info(formatPrefix, ...args);
      }
    },
    warn: (...args: unknown[]) => {
      // Warnings always show
      console.warn(formatPrefix, ...args);
    },
    error: (...args: unknown[]) => {
      // Errors always show
      console.error(formatPrefix, ...args);
    },
  };
}

// Pre-configured loggers for common modules
export const logger = createLogger();
export const dataLogger = createLogger({ prefix: 'DataProvider' });
export const storeLogger = createLogger({ prefix: 'Store' });
export const mockLogger = createLogger({ prefix: 'Mock' });

export { createLogger };
export default logger;
