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
    try {
      const head = await SecureStore.getItemAsync(key);
      if (head == null) return null;
      if (!head.startsWith(CHUNK_MARKER)) return head;
      const count = parseInt(head.slice(CHUNK_MARKER.length), 10);
      if (!Number.isFinite(count) || count <= 0) return null;
      let out = "";
      for (let i = 0; i < count; i++) {
        const part = await SecureStore.getItemAsync(`${key}.${i}`);
        if (part == null) {
          // A missing chunk means a partial/corrupt write — treat the whole
          // value as absent rather than hand Supabase a truncated session.
          logger.warn(`[secureStore] missing chunk ${i + 1}/${count} for ${key}`);
          return null;
        }
        out += part;
      }
      return out;
    } catch (err) {
      logger.error("[secureStore] getItem failed:", err);
      return null;
    }
  },

  setItem: async (key: string, value: string): Promise<void> => {
    if (isWeb) {
      globalThis.localStorage?.setItem(key, value);
      return;
    }
    try {
      // Clear any previous chunk tail first so we never leave a stale chunk.
      await clearChunks(key);
      if (value.length <= CHUNK_LIMIT) {
        await SecureStore.setItemAsync(key, value);
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
    } catch (err) {
      logger.error("[secureStore] setItem failed — session will not persist:", err);
    }
  },

  removeItem: async (key: string): Promise<void> => {
    if (isWeb) {
      globalThis.localStorage?.removeItem(key);
      return;
    }
    try {
      await clearChunks(key);
      await SecureStore.deleteItemAsync(key);
    } catch (err) {
      logger.error("[secureStore] removeItem failed:", err);
    }
  },
};
