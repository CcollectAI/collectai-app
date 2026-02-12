/**
 * Central frontend configuration.
 *
 * Every environment-variable-backed constant used by the React Native /
 * Expo app should be exported from THIS file.  Other modules should
 * `import { ... } from '@/api/config'` instead of reading process.env
 * directly.
 */

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/** FastAPI backend base URL */
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';

if (!API_BASE && typeof __DEV__ !== 'undefined') {
  // eslint-disable-next-line no-console
  console.error('[config] EXPO_PUBLIC_API_BASE_URL is not set — API calls will fail');
}

// ---------------------------------------------------------------------------
// Supabase
// ---------------------------------------------------------------------------

/** Supabase project URL (e.g. https://xyz.supabase.co) */
export const SUPABASE_URL: string | undefined = process.env.EXPO_PUBLIC_SUPABASE_URL;

/** Supabase anonymous/public key */
export const SUPABASE_ANON_KEY: string | undefined = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

/** Supabase mode: 'strict' | 'mock' | 'off' (default: 'mock') */
export const SUPABASE_MODE: string = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? 'mock').toLowerCase();
