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
    // best-effort: __DEV__ detection. This IS the logger, so it cannot log
    // its own bootstrap failure without recursing. Defaulting to dev mode is
    // the safe side: it prints more, never less.
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
  const entry: RetainedLog = {
    level,
    at: new Date().toISOString(),
    message: `${prefix} ${message}`.trim(),
  };
  buffer.push(entry);
  if (buffer.length > LOG_BUFFER_LIMIT) buffer.shift();
  notifySink(entry);
}

/**
 * Optional forwarder for retained logs (see setLogSink).
 *
 * INJECTED, never imported. This file must not `import * as Sentry` — it is
 * the one module that has to keep working when everything else is
 * misbehaving, and the logger having its own dependency is how you get a
 * failure that cannot report itself. app/_layout.tsx owns the Sentry import
 * and registers a sink there.
 */
export type LogSink = (entry: RetainedLog) => void;

let sink: LogSink | null = null;
let inSink = false;

/**
 * Register (or clear, with null) a forwarder called for every retained log.
 *
 * Reentrancy is NOT theoretical here. Sentry's `beforeSend` and
 * `beforeBreadcrumb` hooks in app/_layout.tsx both call `logger.error(...)`
 * from their own catch blocks. Without the `inSink` latch, a sink that hands
 * the entry to Sentry would re-enter this function from inside Sentry's own
 * hook and recurse until the stack blew — turning the diagnostic channel into
 * the crash it was added to report.
 */
export function setLogSink(fn: LogSink | null): void {
  sink = fn;
}

function notifySink(entry: RetainedLog): void {
  if (!sink || inSink) return;
  inSink = true;
  try {
    sink(entry);
  } catch {
    // best-effort: a broken sink must never break logging, and must never be
    // reported THROUGH the sink — that is an infinite loop, not a diagnostic.
    // The entry is already in the ring buffer, which is the durable copy, so
    // the failure is recoverable by reading that rather than by a log line.
  } finally {
    inSink = false;
  }
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
