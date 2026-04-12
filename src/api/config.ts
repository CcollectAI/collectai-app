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
export const API_BASE: string = (() => {
  const envUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (envUrl) return envUrl;
  if (typeof __DEV__ !== 'undefined' && __DEV__) {
     
    console.warn('[config] EXPO_PUBLIC_API_BASE_URL is not set — using localhost fallback');
    return 'http://localhost:8000';
  }
  // Production: fail loudly rather than silently calling localhost
  throw new Error(
    '[config] EXPO_PUBLIC_API_BASE_URL must be set in production builds. ' +
    'Add it to your eas.json env or .env file.',
  );
})();

// ---------------------------------------------------------------------------
// Supabase
// ---------------------------------------------------------------------------

/** Supabase project URL (e.g. https://xyz.supabase.co) */
export const SUPABASE_URL: string | undefined = process.env.EXPO_PUBLIC_SUPABASE_URL;

/** Supabase anonymous/public key */
export const SUPABASE_ANON_KEY: string | undefined = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

/** Supabase mode: 'strict' | 'mock' | 'off' (default: 'mock') */
export const SUPABASE_MODE: string = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? 'mock').toLowerCase();

// Warn if a non-dev build is running with mock data (likely a misconfigured release)
if (SUPABASE_MODE === 'mock' && typeof __DEV__ !== 'undefined' && !__DEV__) {
   
  console.error(
    '[config] WARNING: Production build running with SUPABASE_MODE=mock. ' +
    'This is likely a misconfigured build. Set EXPO_PUBLIC_SUPABASE_MODE=strict for production.',
  );
  // Report to Sentry if available
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Sentry = require('@sentry/react-native');
    Sentry.captureMessage('Production build running with SUPABASE_MODE=mock', 'warning');
  } catch {
    // Sentry not available — console.error above is sufficient
  }
}
