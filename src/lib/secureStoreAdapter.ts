/**
 * SecureStore adapter for Supabase session persistence.
 *
 * Uses expo-secure-store (encrypted keychain on iOS, encrypted SharedPreferences
 * on Android) instead of AsyncStorage for JWT token storage.
 *
 * CHUNKING (2026-07-22): expo-secure-store warns — and on some OS versions
 * outright fails — when a single value exceeds ~2048 bytes. A Supabase session
 * (access JWT + rotating refresh token + the full user object) routinely blows
 * past that, so storing it as ONE value silently dropped the session on native.
 * getSession() then returned null → getAuthHeaders() had no bearer token → every
 * authenticated API call came back 401 ("Authentication required"). That is the
 * long-standing tokenless-401: the earlier httpClient retry treated the symptom,
 * but the session was never actually persisting. We now transparently split an
 * oversized value across `key.0`, `key.1`, … with a small marker at `key`, and
 * reassemble on read. Values under the limit are stored as-is (unchanged shape).
 */

import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import logger from "@/utils/logger";

// Stay comfortably under the 2048-byte warning threshold. JWTs/base64 are ASCII
// so char length ≈ byte length; the margin covers the occasional multi-byte
// char in the user object.
const CHUNK_LIMIT = 1800;
// Sentinel written to the base key when a value is chunked, followed by the
// chunk count, e.g. "__sczk__:3". A real Supabase value (session JSON starts
// with "{", code-verifier is base64) never starts with this.
const CHUNK_MARKER = "__sczk__:";

const isWeb = Platform.OS === "web";

// Write-through memory copy of what this process last read or wrote (2026-09-26).
// supabase-js reads storage on EVERY getSession() — so on every authed API
// request, via getAuthHeaders — and each read here was a head plus N chunk
// decrypts from the keystore, one after another: ~0.3 s normally, 2.6-3.6 s
// measured under load on the emulator, all while holding GoTrue's lock. Only
// this process writes these keys, so the copy is the stored bytes. Entries are
// set only after a SUCCESSFUL read/write and dropped on a failed one, so a
// write that did not persist is never reported back as persisted.
const memory = new Map<string, string | null>();
// Bumped by every write/remove. A read only records what it read if no write
// started while it was in flight — otherwise a slow read of the OLD session
// could land after the new one and hand out a rotated refresh token, which
// Supabase answers by revoking the session (docs/AUTH_AND_WEB_DEPLOY.md).
const generation = new Map<string, number>();
const bump = (key: string) => generation.set(key, (generation.get(key) ?? 0) + 1);
const remember = (key: string, gen: number, value: string | null) => {
  if ((generation.get(key) ?? 0) === gen) memory.set(key, value);
};

/** Tests only: forget the memory copy. */
export function __resetSecureStoreMemory(): void {
  memory.clear();
}

// Remove any chunk tail left over from a previous oversized write for `key`.
async function clearChunks(key: string): Promise<void> {
  try {
    const head = await SecureStore.getItemAsync(key);
    if (head && head.startsWith(CHUNK_MARKER)) {
      const count = parseInt(head.slice(CHUNK_MARKER.length), 10);
      if (Number.isFinite(count)) {
        for (let i = 0; i < count; i++) {
          await SecureStore.deleteItemAsync(`${key}.${i}`);
        }
      }
    }
  } catch (e) {
    logger.error('[silent-catch] secureStoreAdapter.ts:46:', e);
    /* best effort — a failed cleanup just leaves orphaned chunks */
  }
}

/**
 * Supabase expects a storage adapter with getItem/setItem/removeItem.
 * On web (where SecureStore is unavailable), falls back to localStorage.
 *
 * All native calls are wrapped in try/catch — SecureStore can throw on
 * device storage exhaustion, keychain unavailable, or after a restore.
 * Failures are logged but never bubble up to Supabase (which would crash
 * the auth flow). A failed setItem just means the user gets logged out
 * on next launch — annoying, but not catastrophic.
 */
export const secureStoreAdapter = {
  getItem: async (key: string): Promise<string | null> => {
    if (isWeb) {
      return globalThis.localStorage?.getItem(key) ?? null;
    }
    if (memory.has(key)) return memory.get(key) ?? null;
    const gen = generation.get(key) ?? 0;
    // DIAG (2026-09-24). An Android cold start stalled every Supabase request
    // ~15 s behind getSession(), which reads THIS under processLock. Storage
    // turned out NOT to be the cause (2 chunks, ~0.3 s; the cause was an async
    // onAuthStateChange listener — see scripts/check-auth-listener-lock.mjs),
    // but it is the first thing to rule out next time, so it stays: silent
    // unless a read takes over 1.5 s or is still pending after 3 s. Lands in
    // Settings → Diagnostics (logger ring), not Sentry.
    const t0 = Date.now();
    let chunks = 0;
    const slow = () => {
      clearTimeout(pending);
      const ms = Date.now() - t0;
      if (ms > 1500) logger.error(`[DIAG secureStore] getItem ${key} took ${ms}ms (${chunks} chunk(s))`);
    };
    const pending = setTimeout(() => logger.error(`[DIAG secureStore] getItem ${key} STILL PENDING after 3000ms (${chunks} chunk(s) read)`), 3000);
    try {
      const head = await SecureStore.getItemAsync(key);
      if (head == null) { slow(); remember(key, gen, null); return null; }
      if (!head.startsWith(CHUNK_MARKER)) { slow(); remember(key, gen, head); return head; }
      const count = parseInt(head.slice(CHUNK_MARKER.length), 10);
      if (!Number.isFinite(count) || count <= 0) { slow(); return null; }
      // In parallel: the chunks are independent keys, and reading them one
      // after another multiplied the keystore latency by the chunk count.
      const parts = await Promise.all(
        Array.from({ length: count }, (_, i) => SecureStore.getItemAsync(`${key}.${i}`)),
      );
      chunks = count;
      const missing = parts.findIndex((p) => p == null);
      if (missing >= 0) {
        // A missing chunk means a partial/corrupt write — treat the whole
        // value as absent rather than hand Supabase a truncated session.
        logger.warn(`[secureStore] missing chunk ${missing + 1}/${count} for ${key}`);
        slow();
        return null;
      }
      const out = parts.join("");
      slow();
      remember(key, gen, out);
      return out;
    } catch (err) {
      clearTimeout(pending);
      logger.error("[secureStore] getItem failed:", err);
      // empty-ok: this is supabase-js's auth storage. null = no stored session,
      // the contract its hydrate expects; a throw here breaks session restore
      // (docs/AUTH_AND_WEB_DEPLOY.md — do not change auth behaviour).
      return null;
    }
  },

  setItem: async (key: string, value: string): Promise<void> => {
    if (isWeb) {
      globalThis.localStorage?.setItem(key, value);
      return;
    }
    bump(key);
    const myGen = generation.get(key) ?? 0;
    memory.delete(key); // until this write lands, the store is the only truth
    try {
      // Clear any previous chunk tail first so we never leave a stale chunk.
      await clearChunks(key);
      if (value.length <= CHUNK_LIMIT) {
        await SecureStore.setItemAsync(key, value);
        remember(key, myGen, value); // a later write wins, even if it finished first
        return;
      }
      const count = Math.ceil(value.length / CHUNK_LIMIT);
      for (let i = 0; i < count; i++) {
        await SecureStore.setItemAsync(
          `${key}.${i}`,
          value.slice(i * CHUNK_LIMIT, (i + 1) * CHUNK_LIMIT),
        );
      }
      // Write the marker LAST: a crash mid-write then leaves the old value or
      // nothing, never a marker pointing at missing chunks.
      await SecureStore.setItemAsync(key, `${CHUNK_MARKER}${count}`);
      remember(key, myGen, value);
    } catch (err) {
      memory.delete(key); // the next read must ask the store what actually persisted
      logger.error("[secureStore] setItem failed — session will not persist:", err);
    }
  },

  removeItem: async (key: string): Promise<void> => {
    if (isWeb) {
      globalThis.localStorage?.removeItem(key);
      return;
    }
    bump(key);
    const myGen = generation.get(key) ?? 0;
    memory.delete(key);
    try {
      await clearChunks(key);
      await SecureStore.deleteItemAsync(key);
      remember(key, myGen, null);
    } catch (err) {
      memory.delete(key);
      logger.error("[secureStore] removeItem failed:", err);
    }
  },
};
