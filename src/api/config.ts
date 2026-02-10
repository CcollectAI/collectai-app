// API base URL — MUST be set via EXPO_PUBLIC_API_BASE_URL in .env
// Do NOT hardcode IP addresses or secrets here.
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL ?? '';

if (!API_BASE && typeof __DEV__ !== 'undefined') {
  // eslint-disable-next-line no-console
  console.error('[config] EXPO_PUBLIC_API_BASE_URL is not set — API calls will fail');
}
