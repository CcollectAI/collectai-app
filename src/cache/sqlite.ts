import * as SQLite from "expo-sqlite";
import { logger } from '@/lib/logger';

let _db: SQLite.SQLiteDatabase | null = null;
export function db() {
  if (_db) return _db;
  _db = SQLite.openDatabaseSync("collectors.db");
  _db.execSync(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL);
  `);
  return _db!;
}

export function cacheSet(key: string, obj: unknown) {
  const d = db();
  const val = JSON.stringify(obj);
  const now = Date.now();
  d.runSync("INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?, ?, ?)", [key, val, now]);
}

export function cacheGet<T = unknown>(key: string): { value: T | null; ageMs: number } {
  const d = db();
  const row = d.getFirstSync<{ value: string; updated_at: number }>("SELECT value, updated_at FROM kv WHERE key = ?", [key]);
  if (!row) return { value: null, ageMs: Infinity };
  try {
    return { value: JSON.parse(row.value), ageMs: Date.now() - row.updated_at };
  } catch (e) {
    logger.error('[silent-catch] sqlite.ts:27:', e);
    return { value: null, ageMs: Infinity };
  }
}
