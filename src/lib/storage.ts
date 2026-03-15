
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const s = await AsyncStorage.getItem(key);
    return s ? JSON.parse(s) as T : fallback;
  } catch (e) {
    logger.debug('[storage] getJSON failed for key:', key, e);
    return fallback;
  }
}
export async function setJSON<T>(key: string, value: T): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    logger.debug('[storage] setJSON failed for key:', key, e);
  }
}
export async function removeKey(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch (e) {
    logger.debug('[storage] removeKey failed for key:', key, e);
  }
}
