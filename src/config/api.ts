// Re-export from the canonical config location
export { API_BASE as API_BASE_URL } from '../api/config';

export const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';
