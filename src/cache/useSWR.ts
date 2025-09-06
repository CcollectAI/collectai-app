import { useEffect, useState, useCallback } from "react";
import { cacheGet, cacheSet } from "./sqlite";

type Fetcher<T> = () => Promise<T>;
type Options = { staleMs?: number };

export function useSWR<T>(key: string, fetcher: Fetcher<T>, opts: Options = {}) {
  const staleMs = opts.staleMs ?? 60_000;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await fetcher();
      setData(fresh as any);
      cacheSet(key, fresh);
    } finally {
      setLoading(false);
    }
  }, [key, fetcher]);

  useEffect(() => {
    const { value, ageMs } = cacheGet<T>(key);
    if (value) setData(value);
    setLoading(!value);
    if (ageMs > staleMs || !value) {
      load().catch(() => {});
    }
  }, [key, staleMs, load]);

  return { data, loading, refresh: load };
}
