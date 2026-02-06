// API base URL — reads from env, falls back to EC2 for production.
// In development, set EXPO_PUBLIC_API_BASE_URL in .env
export const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://3.75.182.41:8000';
