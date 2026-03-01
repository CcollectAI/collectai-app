/**
 * SecureStore adapter for Supabase session persistence.
 *
 * Uses expo-secure-store (encrypted keychain on iOS, encrypted SharedPreferences
 * on Android) instead of AsyncStorage for JWT token storage.
 */

import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

/**
 * Supabase expects a storage adapter with getItem/setItem/removeItem.
 * On web (where SecureStore is unavailable), falls back to localStorage.
 */
export const secureStoreAdapter = {
  getItem: async (key: string): Promise<string | null> => {
    if (Platform.OS === "web") {
      return globalThis.localStorage?.getItem(key) ?? null;
    }
    return SecureStore.getItemAsync(key);
  },

  setItem: async (key: string, value: string): Promise<void> => {
    if (Platform.OS === "web") {
      globalThis.localStorage?.setItem(key, value);
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },

  removeItem: async (key: string): Promise<void> => {
    if (Platform.OS === "web") {
      globalThis.localStorage?.removeItem(key);
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
