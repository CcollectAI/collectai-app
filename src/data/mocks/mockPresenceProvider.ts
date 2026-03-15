/**
 * Mock presence domain provider.
 */

import type { UserPresence } from '../types';

export async function sendHeartbeat(): Promise<void> { /* no-op */ }
export async function goOffline(): Promise<void> { /* no-op */ }

export async function getUserPresence(userId: string): Promise<UserPresence | null> {
  return { userId, lastSeenAt: new Date().toISOString(), isOnline: true };
}

export async function getBatchPresence(userIds: string[]): Promise<UserPresence[]> {
  return userIds.map((userId) => ({ userId, lastSeenAt: new Date().toISOString(), isOnline: true }));
}
