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

// ── Retained log buffer ────────────────────────────────────────────────────
// debug/info are not printed in release builds, and until now that meant they
// were simply LOST: 139 catch blocks logged a failure via warn/info and left
// no trace whatsoever in the build where it mattered, so a real backend
// failure was indistinguishable from "no data".
//
// Instead of rewriting 181 call sites, keep them. Every level is appended to a
// bounded in-memory ring regardless of whether it is printed, so a failure is
// always recoverable via getRecentLogs() from the diagnostics screen. Console
// noise stays exactly as it was; only the retention changes.
const LOG_BUFFER_LIMIT = 300;

export interface RetainedLog {
  level: LogLevel;
  at: string;
  message: string;
}

const buffer: RetainedLog[] = [];

function retain(level: LogLevel, prefix: string, args: unknown[]) {
  let message: string;
  try {
    message = args
      .map((a) => {
        if (typeof a === 'string') return a;
        if (a instanceof Error) return `${a.name}: ${a.message}`;
        return JSON.stringify(a);
      })
      .join(' ');
  } catch {
    // best-effort: a circular or exotic payload must never break logging
    // itself, which is the one thing that has to keep working when the app
    // is misbehaving.
    message = args.map((a) => String(a)).join(' ');
  }
  buffer.push({ level, at: new Date().toISOString(), message: `${prefix} ${message}`.trim() });
  if (buffer.length > LOG_BUFFER_LIMIT) buffer.shift();
}

/** Most recent retained logs, newest last. Optionally filtered by level. */
export function getRecentLogs(minLevel: LogLevel = 'debug'): RetainedLog[] {
  const rank: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 };
  return buffer.filter((l) => rank[l.level] >= rank[minLevel]);
}

/** Clears the retained buffer (used by the diagnostics screen). */
export function clearRecentLogs(): void {
  buffer.length = 0;
}

function createLogger(options: LoggerOptions = {}) {
  const { prefix = '', enabled = isDev } = options;
  const formatPrefix = prefix ? `[${prefix}]` : '';

  return {
    debug: (...args: unknown[]) => {
      retain('debug', formatPrefix, args);
      if (enabled) {
        console.log(formatPrefix, ...args);
      }
    },
    info: (...args: unknown[]) => {
      retain('info', formatPrefix, args);
      if (enabled) {
        console.info(formatPrefix, ...args);
      }
    },
    warn: (...args: unknown[]) => {
      retain('warn', formatPrefix, args);
      // Warnings always show
      console.warn(formatPrefix, ...args);
    },
    error: (...args: unknown[]) => {
      retain('error', formatPrefix, args);
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
