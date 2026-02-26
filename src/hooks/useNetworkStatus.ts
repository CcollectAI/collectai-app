/**
 * useNetworkStatus — reactive hook for tracking online/offline status.
 *
 * Uses `expo-network` to detect connectivity changes.  Components can use
 * the returned `isOnline` boolean to gate network requests or show
 * offline-aware UI (no visual banner is rendered by this hook).
 *
 * Also exposes an `onReconnect` function that external modules (e.g. the
 * offline mutation queue) can register callbacks on.  When the device
 * transitions from offline -> online, all registered listeners fire.
 *
 * Usage:
 *   const { isOnline } = useNetworkStatus();
 *
 *   // External (non-hook) usage:
 *   import { onReconnect } from '@/hooks/useNetworkStatus';
 *   const unsub = onReconnect(() => replayQueue());
 */

import { useEffect, useRef, useState } from 'react';
import * as Network from 'expo-network';
import logger from '../utils/logger';

export interface NetworkStatus {
  /** `true` when the device has internet connectivity */
  isOnline: boolean;
}

// ── Reconnection listener registry ──────────────────────────────────────────

const reconnectListeners: Set<(connected: boolean) => void> = new Set();

/**
 * Register a callback that fires when the device transitions offline -> online.
 * Returns an unsubscribe function.
 */
export function onReconnect(fn: (connected: boolean) => void): () => void {
  reconnectListeners.add(fn);
  return () => {
    reconnectListeners.delete(fn);
  };
}

// Track the last-known connectivity state for reconnection detection.
// Shared across all hook instances.
let _lastKnownOnline = true;

/**
 * Internal: update the global online state and fire listeners on reconnection.
 */
function handleConnectivityChange(online: boolean): void {
  if (online && !_lastKnownOnline) {
    logger.info('[useNetworkStatus] Reconnected — notifying listeners');
    reconnectListeners.forEach((fn) => {
      try {
        fn(online);
      } catch (err) {
        logger.warn('[useNetworkStatus] reconnect listener error:', err);
      }
    });
  }
  _lastKnownOnline = online;
}

/**
 * Imperatively check whether the device is currently online.
 * Useful outside of React component trees (e.g. in the mutation queue).
 */
export async function isDeviceOnline(): Promise<boolean> {
  try {
    const state = await Network.getNetworkStateAsync();
    return state.isInternetReachable ?? state.isConnected ?? true;
  } catch {
    return true; // optimistic fallback
  }
}

/**
 * Polls network state on mount and subscribes to connectivity changes.
 * Falls back to `true` (optimistic) if detection fails.
 */
export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const prevOnline = useRef(true);

  useEffect(() => {
    let mounted = true;

    // Initial check
    Network.getNetworkStateAsync()
      .then((state) => {
        if (mounted) {
          const online = state.isInternetReachable ?? state.isConnected ?? true;
          setIsOnline(online);
          handleConnectivityChange(online);
          prevOnline.current = online;
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
          handleConnectivityChange(online);
          prevOnline.current = online;
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
