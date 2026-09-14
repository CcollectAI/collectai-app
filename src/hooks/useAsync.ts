import { useState, useEffect, useCallback, useRef, DependencyList } from 'react';
import { userErrorMessage } from '@/lib/userErrorMessage';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  /** Safe to render: a server-written sentence or a generic one, never plumbing. */
  error: string | null;
  /** The raw exception text, for the log only (err.message is for the log). */
  errorDetail: string | null;
  retry: () => void;
}

const GENERIC_LOAD_ERROR = "Couldn't load this. Please try again.";

/**
 * Hook that manages async data fetching with loading/error states.
 * Automatically handles cleanup on unmount to prevent state updates after unmount.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: DependencyList = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const execute = useCallback(() => {
    setLoading(true);
    setError(null);
    setErrorDetail(null);
    fnRef.current()
      .then((result) => {
        if (mountedRef.current) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mountedRef.current) {
          // No logLabel: a shared hook logging here would put every consumer's
          // failure into Sentry, twice for Analytics, which logs errorDetail.
          setError(userErrorMessage(err, GENERIC_LOAD_ERROR));
          setErrorDetail(err instanceof Error ? err.message : String(err)); // raw-error-ok: exposed as errorDetail, for logs
          setLoading(false);
        }
      });
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mountedRef.current = true;
    execute();
    return () => { mountedRef.current = false; };
  }, [execute]);

  return { data, loading, error, errorDetail, retry: execute };
}
