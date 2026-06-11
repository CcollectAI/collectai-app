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
    return state.isConnected !== false;
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

    // isConnected only — isInternetReachable returns false transiently on iOS mid-probe (TestFlight #9 false-positive).
    const computeOnline = (state: Network.NetworkState) => state.isConnected !== false;

    const commit = (online: boolean) => {
      if (!mounted) return;
      setIsOnline(online);
      handleConnectivityChange(online);
      prevOnline.current = online;
    };

    // Evaluate connectivity. A single `isConnected === false` reading is NOT
    // trusted: iOS reports offline transiently during cold start / network-stack
    // warmup, which flashed the orange "You're offline" banner at login for new
    // users (reported 2026-06-11). Re-verify ~1.2s later and only commit offline
    // if it's still offline; online is committed immediately.
    const evaluate = async () => {
      try {
        const state = await Network.getNetworkStateAsync();
        if (computeOnline(state)) {
          commit(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 1200));
        if (!mounted) return;
        try {
          const recheck = await Network.getNetworkStateAsync();
          commit(computeOnline(recheck));
        } catch {
          commit(true); // optimistic on error
        }
      } catch (err) {
        logger.warn('[useNetworkStatus] check failed:', err);
        commit(true); // optimistic on error
      }
    };

    // Initial check + periodic polling (expo-network has no subscription listener)
    evaluate();
    const interval = setInterval(evaluate, 10_000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { isOnline };
}
