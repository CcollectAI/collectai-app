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

/**
 * WHOSE data this cache holds. Keys are not per-user (`watchlist:list`,
 * `items:list`, `portfolio:summary` …), and nothing cleared them when the
 * signed-in member changed — so the next account on the phone was served the
 * previous one's watchlist, items and portfolio until each TTL ran out, and a
 * read made before sign-in completed (0 rows under RLS, no error) kept
 * answering "No items in your watchlist yet" to a member with six (walked on
 * Android 2026-09-24). `bindCacheOwner` is the one place that decides; every
 * read and write waits for the latest binding, so nothing can read the old
 * member's rows between "user changed" and "cache cleared".
 */
const OWNER_KEY = '__cache_owner__';
// Never rejects: bindCacheOwner's body catches everything and resolves false,
// so awaiting it needs no .catch.
let _ownerBinding: Promise<boolean> = Promise.resolve(false);
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
  await _ownerBinding;
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
    logger.error('[offlineCache] cacheGet error:', err);
    // empty-ok: null is a cache MISS, never rendered as data — every caller
    // (swr in CachedDataProvider, catalogBrowseCache, inbox) falls through to
    // the network on null, so a broken cache costs a fetch, not a false empty.
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
  await _ownerBinding;
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
    logger.error('[offlineCache] cacheSet error:', err);
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
    logger.error('[offlineCache] cacheClear error:', err);
  }
}

/**
 * Bind the cache to the signed-in member (null = signed out). Wipes every entry
 * when the owner differs from the one stored with the cache — including on a
 * cold start after an account switch, since the owner is persisted. Resolves
 * true when it wiped, so callers can reset their in-memory copies too.
 */
export function bindCacheOwner(userId: string | null): Promise<boolean> {
  const previous = _ownerBinding;
  _ownerBinding = (async () => {
    await previous;
    if (IS_WEB) return false;
    try {
      const db = await getDb();
      if (!db) return false;
      const row = await (db.getFirstAsync as any)('SELECT data FROM cache WHERE key = ?', [OWNER_KEY]);
      const stored: string | null = row ? JSON.parse(row.data) : null;
      const next = userId ?? null;
      if (stored === next) return false;
      await db.runAsync('DELETE FROM cache');
      await db.runAsync(
        'INSERT OR REPLACE INTO cache (key, data, expires_at) VALUES (?, ?, ?)',
        [OWNER_KEY, JSON.stringify(next), Number.MAX_SAFE_INTEGER],
      );
      logger.info('[offlineCache] owner changed — cleared all entries');
      return true;
    } catch (err) {
      logger.error('[offlineCache] bindCacheOwner error:', err);
      return false;
    }
  })();
  return _ownerBinding;
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
  _ownerBinding = Promise.resolve(false);
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
    logger.error('[offlineCache] cacheEvictExpired error:', err);
    // empty-ok: housekeeping count, rendered nowhere; expired rows are also
    // pruned lazily by cacheGet.
    return 0;
  }
}
