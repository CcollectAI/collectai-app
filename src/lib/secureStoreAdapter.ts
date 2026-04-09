/**
 * SecureStore adapter for Supabase session persistence.
 *
 * Uses expo-secure-store (encrypted keychain on iOS, encrypted SharedPreferences
 * on Android) instead of AsyncStorage for JWT token storage.
 */

import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import logger from "@/utils/logger";

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
    if (Platform.OS === "web") {
      return globalThis.localStorage?.getItem(key) ?? null;
    }
    try {
      return await SecureStore.getItemAsync(key);
    } catch (err) {
      logger.warn("[secureStore] getItem failed:", err);
      return null;
    }
  },

  setItem: async (key: string, value: string): Promise<void> => {
    if (Platform.OS === "web") {
      globalThis.localStorage?.setItem(key, value);
      return;
    }
    try {
      await SecureStore.setItemAsync(key, value);
    } catch (err) {
      logger.warn("[secureStore] setItem failed — session will not persist:", err);
    }
  },

  removeItem: async (key: string): Promise<void> => {
    if (Platform.OS === "web") {
      globalThis.localStorage?.removeItem(key);
      return;
    }
    try {
      await SecureStore.deleteItemAsync(key);
    } catch (err) {
      logger.warn("[secureStore] removeItem failed:", err);
    }
  },
};
