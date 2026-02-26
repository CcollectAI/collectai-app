/**
 * usePresenceHeartbeat — Sends periodic heartbeat to track online status.
 * Call once at the root layout level after auth has resolved.
 */
import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import { dataProvider } from '@/data';

const HEARTBEAT_INTERVAL_MS = 60_000; // 60 seconds

export function usePresenceHeartbeat(userId: string | null) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!userId) return;

    // Send initial heartbeat
    dataProvider.sendHeartbeat().catch(() => {});

    // Set up interval
    intervalRef.current = setInterval(() => {
      dataProvider.sendHeartbeat().catch(() => {});
    }, HEARTBEAT_INTERVAL_MS);

    // Listen for app state changes
    const subscription = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'active') {
        dataProvider.sendHeartbeat().catch(() => {});
      } else if (state === 'background' || state === 'inactive') {
        dataProvider.goOffline().catch(() => {});
      }
    });

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      subscription.remove();
      dataProvider.goOffline().catch(() => {});
    };
  }, [userId]);
}
