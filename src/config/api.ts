export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8080';

export const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';

if (!process.env.EXPO_PUBLIC_API_BASE_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    '[config/api] EXPO_PUBLIC_API_BASE_URL is not set; falling back to http://127.0.0.1:8080'
  );
}
