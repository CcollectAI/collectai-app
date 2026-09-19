
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const s = await AsyncStorage.getItem(key);
    return s ? JSON.parse(s) as T : fallback;
  } catch (e) {
    logger.error('[storage] getJSON failed for key:', key, e);
    return fallback;
  }
}
/**
 * Returns whether the write landed.
 *
 * It swallowed and returned void until 2026-09-19, and `users/[userId].tsx` did
 *     await setJSON('followed_users', ids);
 *     showToast({ message: 'Following!', type: 'success' });
 * so a failed write told the member it had worked — and `followed_users` lives
 * ONLY here, with no server copy, so the follow was gone on next launch. That
 * is class Z: a success message not conditional on success. The likeliest cause
 * of a failed write is a full device, which is also when a member has the most
 * cached and the most to lose.
 *
 * Still swallows the exception — callers should not have to try/catch a cache
 * write — but the boolean lets one that is making a CLAIM check it. Existing
 * callers that ignore the return are unaffected.
 */
export async function setJSON<T>(key: string, value: T): Promise<boolean> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (e) {
    logger.error('[storage] setJSON failed for key:', key, e);
    return false;
  }
}
export async function removeKey(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch (e) {
    logger.error('[storage] removeKey failed for key:', key, e);
  }
}
