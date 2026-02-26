/**
 * offlineCache — SQLite-backed key/value cache for offline-first support.
 *
 * Uses expo-sqlite to persist cached responses locally so the app can serve
 * stale data while the network is unavailable.
 *
 * On web, SQLite is not available — all operations gracefully no-op.
 *
 * Schema:
 *   CREATE TABLE IF NOT EXISTS cache (
 *     key        TEXT PRIMARY KEY,
 *     data       TEXT NOT NULL,
 *     expires_at INTEGER NOT NULL   -- unix epoch ms
 *   )
 *
 * Public API:
 *   cacheGet(key)             — returns parsed JSON or null (expired entries removed lazily)
 *   cacheSet(key, data, ttl)  — upserts a cache entry
 *   cacheClear(prefix?)       — deletes matching entries (all if no prefix)
 */

import { Platform } from 'react-native';
import logger from '../utils/logger';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DB_NAME = 'collectai_cache.db';
const DEFAULT_TTL_MS = 5 * 60 * 1000; // 5 minutes
const IS_WEB = Platform.OS === 'web';

// ---------------------------------------------------------------------------
// Database singleton (native only)
// ---------------------------------------------------------------------------

let _db: any = null;
let _initPromise: Promise<void> | null = null;

async function getDb(): Promise<any> {
  if (IS_WEB) return null;
  if (_db) return _db;
  if (_initPromise) {
    await _initPromise;
    return _db!;
  }

  _initPromise = (async () => {
    try {
      const SQLite = await import('expo-sqlite');
      _db = await SQLite.openDatabaseAsync(DB_NAME);
      await _db.execAsync(
        `CREATE TABLE IF NOT EXISTS cache (
          key        TEXT PRIMARY KEY,
          data       TEXT NOT NULL,
          expires_at INTEGER NOT NULL
        );`
      );
      logger.info('[offlineCache] database initialised');
    } catch (err) {
      logger.error('[offlineCache] failed to initialise database:', err);
      throw err;
    }
  })();

  await _initPromise;
  return _db!;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Retrieve a cached value by key.
 * Returns `null` when the key is missing or has expired.
 * Expired rows are deleted lazily on read.
 */
export async function cacheGet<T = unknown>(key: string): Promise<T | null> {
  if (IS_WEB) return null;
  try {
    const db = await getDb();
    if (!db) return null;
    const now = Date.now();

    const row = await (db.getFirstAsync as any)(
      'SELECT data, expires_at FROM cache WHERE key = ?',
      [key],
    );

    if (!row) return null;

    // Check TTL — delete if expired
    if (row.expires_at <= now) {
      await db.runAsync('DELETE FROM cache WHERE key = ?', [key]);
      return null;
    }

    return JSON.parse(row.data) as T;
  } catch (err) {
    logger.warn('[offlineCache] cacheGet error:', err);
    return null;
  }
}

/**
 * Store a value in the cache.
 *
 * @param key    Cache key (e.g. `items:list`, `portfolio:summary`)
 * @param data   Any JSON-serialisable value
 * @param ttlMs  Time-to-live in milliseconds (default: 5 minutes)
 */
export async function cacheSet(
  key: string,
  data: unknown,
  ttlMs: number = DEFAULT_TTL_MS,
): Promise<void> {
  if (IS_WEB) return;
  try {
    const db = await getDb();
    if (!db) return;
    const expiresAt = Date.now() + ttlMs;
    const serialised = JSON.stringify(data);

    await db.runAsync(
      `INSERT OR REPLACE INTO cache (key, data, expires_at) VALUES (?, ?, ?)`,
      [key, serialised, expiresAt],
    );
  } catch (err) {
    logger.warn('[offlineCache] cacheSet error:', err);
  }
}

/**
 * Delete cache entries.
 *
 * @param prefix  If provided, only keys starting with this prefix are deleted.
 *                If omitted, the entire cache is wiped.
 */
export async function cacheClear(prefix?: string): Promise<void> {
  if (IS_WEB) return;
  try {
    const db = await getDb();
    if (!db) return;

    if (prefix) {
      // Delete all keys that start with the given prefix
      await db.runAsync(
        'DELETE FROM cache WHERE key LIKE ?',
        [`${prefix}%`],
      );
      logger.info(`[offlineCache] cleared keys with prefix "${prefix}"`);
    } else {
      await db.runAsync('DELETE FROM cache');
      logger.info('[offlineCache] cleared all entries');
    }
  } catch (err) {
    logger.warn('[offlineCache] cacheClear error:', err);
  }
}

/**
 * Remove all expired entries.  Can be called periodically to keep the
 * database tidy, but is not required — expired entries are also pruned
 * lazily by `cacheGet`.
 */
/** @internal Inject a mock db and reset state — for testing only. */
export function __setDbForTesting(db: any): void {
  _db = db;
  _initPromise = Promise.resolve();
}

export async function cacheEvictExpired(): Promise<number> {
  if (IS_WEB) return 0;
  try {
    const db = await getDb();
    if (!db) return 0;
    const result = await db.runAsync(
      'DELETE FROM cache WHERE expires_at <= ?',
      [Date.now()],
    );
    const deleted = result.changes;
    if (deleted > 0) {
      logger.info(`[offlineCache] evicted ${deleted} expired entries`);
    }
    return deleted;
  } catch (err) {
    logger.warn('[offlineCache] cacheEvictExpired error:', err);
    return 0;
  }
}
