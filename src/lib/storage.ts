
import AsyncStorage from '@react-native-async-storage/async-storage';

export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const s = await AsyncStorage.getItem(key);
    return s ? JSON.parse(s) as T : fallback;
  } catch {
    return fallback;
  }
}
export async function setJSON<T>(key: string, value: T): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {}
}
export async function removeKey(key: string): Promise<void> {
  try { await AsyncStorage.removeItem(key); } catch {}
}
