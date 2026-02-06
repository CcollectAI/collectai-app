// Re-export from the canonical config location
export { API_BASE as API_BASE_URL } from '../api/config';

export const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';

if (!process.env.EXPO_PUBLIC_API_BASE_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    '[config/api] EXPO_PUBLIC_API_BASE_URL is not set; falling back to EC2 default'
  );
}
