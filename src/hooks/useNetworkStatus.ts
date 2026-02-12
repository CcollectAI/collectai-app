/**
 * useNetworkStatus — reactive hook for tracking online/offline status.
 *
 * Uses `expo-network` to detect connectivity changes.  Components can use
 * the returned `isOnline` boolean to gate network requests or show
 * offline-aware UI (no visual banner is rendered by this hook).
 *
 * Usage:
 *   const { isOnline } = useNetworkStatus();
 */

import { useEffect, useState } from 'react';
import * as Network from 'expo-network';
import logger from '../utils/logger';

export interface NetworkStatus {
  /** `true` when the device has internet connectivity */
  isOnline: boolean;
}

/**
 * Polls network state on mount and subscribes to connectivity changes.
 * Falls back to `true` (optimistic) if detection fails.
 */
export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;

    // Initial check
    Network.getNetworkStateAsync()
      .then((state) => {
        if (mounted) {
          const online = state.isInternetReachable ?? state.isConnected ?? true;
          setIsOnline(online);
        }
      })
      .catch((err) => {
        logger.warn('[useNetworkStatus] initial check failed:', err);
        // Assume online on error
        if (mounted) setIsOnline(true);
      });

    // Periodic polling (expo-network does not expose a subscription listener)
    // Poll every 10 seconds to detect connectivity changes.
    const interval = setInterval(async () => {
      try {
        const state = await Network.getNetworkStateAsync();
        if (mounted) {
          const online = state.isInternetReachable ?? state.isConnected ?? true;
          setIsOnline(online);
        }
      } catch {
        // Silently ignore polling errors
      }
    }, 10_000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { isOnline };
}
