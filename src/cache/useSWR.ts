import { useEffect, useState, useCallback } from "react";
import { cacheGet, cacheSet } from "./sqlite";
import { logger } from "@/lib/logger";

type Fetcher<T> = () => Promise<T>;
type Options = { staleMs?: number };

// 2026-04-20 round-4 silent-failure sweep: the prior `.catch(() => {})`
// on load() swallowed every fetch error, leaving stale cache as `data`
// and `loading=false` — the consumer had no way to distinguish fresh
// data from an error that reused old cache. We now expose an `error`
// state so callers can render error banners instead of silently showing
// stale data as current.
export function useSWR<T>(key: string, fetcher: Fetcher<T>, opts: Options = {}) {
  const staleMs = opts.staleMs ?? 60_000;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const fresh = await fetcher();
      setData(fresh);
      cacheSet(key, fresh);
    } catch (err) {
      logger.warn("[useSWR] fetch failed for", key, err);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [key, fetcher]);

  useEffect(() => {
    const { value, ageMs } = cacheGet<T>(key);
    if (value) setData(value);
    setLoading(!value);
    if (ageMs > staleMs || !value) {
      void load();
    }
  }, [key, staleMs, load]);

  return { data, loading, error, refresh: load };
}
