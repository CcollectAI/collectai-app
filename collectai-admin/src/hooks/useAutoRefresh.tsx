"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface UseAutoRefreshOptions {
  callback: () => void | Promise<void>;
  interval: number;
  enabled?: boolean;
}

interface UseAutoRefreshReturn {
  isRefreshing: boolean;
  lastRefresh: Date | null;
  toggleEnabled: () => void;
  enabled: boolean;
}

export function useAutoRefresh({
  callback,
  interval,
  enabled: initialEnabled = true,
}: UseAutoRefreshOptions): UseAutoRefreshReturn {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [enabled, setEnabled] = useState(initialEnabled);
  const callbackRef = useRef(callback);

  // Keep callback ref up to date without re-triggering the effect
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  const executeCallback = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await callbackRef.current();
    } finally {
      setIsRefreshing(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // Call immediately on mount / when enabled
    executeCallback();

    const id = setInterval(executeCallback, interval);
    return () => clearInterval(id);
  }, [enabled, interval, executeCallback]);

  const toggleEnabled = useCallback(() => {
    setEnabled((prev) => !prev);
  }, []);

  return { isRefreshing, lastRefresh, toggleEnabled, enabled };
}
