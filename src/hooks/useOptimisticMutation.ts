/**
 * useOptimisticMutation
 *
 * Generic hook for optimistic UI updates on mutations.
 *
 * Flow:
 *  1. Caller invokes `mutate(args)`.
 *  2. The `onOptimisticUpdate` callback fires synchronously to update local
 *     state (e.g. remove item from list, toggle RSVP flag).
 *  3. The real `mutationFn` runs in the background.
 *  4. On success, the optional `onSuccess` callback fires (e.g. replace temp
 *     ID with real server ID).
 *  5. On error, `onRollback` fires to revert the optimistic change, and the
 *     error is surfaced via the returned `error` state.
 *
 * Usage:
 *   const { mutate, isLoading, error } = useOptimisticMutation({
 *     mutationFn: (id: string) => dataProvider.deleteItem(id),
 *     onOptimisticUpdate: (id) => setItems(prev => prev.filter(i => i.id !== id)),
 *     onRollback: (id, err) => loadItems(),
 *   });
 */

import { useState, useCallback, useRef } from 'react';
import logger from '@/utils/logger';

export type OptimisticMutationConfig<TArgs, TResult = void> = {
  /**
   * The actual async mutation that talks to the server / data provider.
   */
  mutationFn: (args: TArgs) => Promise<TResult>;

  /**
   * Called synchronously before the mutation starts.
   * Use this to apply the optimistic state change (remove from list, toggle flag, etc.).
   */
  onOptimisticUpdate: (args: TArgs) => void;

  /**
   * Called when the mutation fails.
   * Use this to revert the optimistic change.
   * Receives the original args and the error.
   */
  onRollback: (args: TArgs, error: Error) => void;

  /**
   * Optional. Called when the mutation succeeds.
   * Use this to reconcile server state (e.g. replace temp ID with real ID).
   */
  onSuccess?: (args: TArgs, result: TResult) => void;
};

export type OptimisticMutationReturn<TArgs> = {
  /** Trigger the optimistic mutation. */
  mutate: (args: TArgs) => Promise<void>;
  /** Whether a mutation is currently in flight. */
  isLoading: boolean;
  /** The most recent error, or null. Cleared on next successful mutate. */
  error: Error | null;
};

export function useOptimisticMutation<TArgs, TResult = void>(
  config: OptimisticMutationConfig<TArgs, TResult>,
): OptimisticMutationReturn<TArgs> {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Keep config ref stable to avoid stale closure issues in callbacks.
  const configRef = useRef(config);
  configRef.current = config;

  const mutate = useCallback(async (args: TArgs) => {
    const { mutationFn, onOptimisticUpdate, onRollback, onSuccess } = configRef.current;

    // Clear previous error
    setError(null);

    // Step 1: Apply optimistic update immediately (synchronous)
    try {
      onOptimisticUpdate(args);
    } catch (optimisticError) {
      logger.error('[useOptimisticMutation] onOptimisticUpdate threw:', optimisticError);
      // If the optimistic update itself fails, don't proceed with the mutation.
      setError(optimisticError instanceof Error ? optimisticError : new Error(String(optimisticError)));
      return;
    }

    // Step 2: Run the real mutation in the background
    setIsLoading(true);
    try {
      const result = await mutationFn(args);

      // Step 3: On success, call onSuccess if provided (e.g. to reconcile server state)
      if (onSuccess) {
        try {
          onSuccess(args, result);
        } catch (successError) {
          logger.error('[useOptimisticMutation] onSuccess threw:', successError);
        }
      }
    } catch (mutationError) {
      const err = mutationError instanceof Error ? mutationError : new Error(String(mutationError));
      setError(err);

      // Step 4: Rollback the optimistic update
      try {
        onRollback(args, err);
      } catch (rollbackError) {
        logger.error('[useOptimisticMutation] onRollback threw:', rollbackError);
      }

      logger.error('[useOptimisticMutation] mutation failed, rolled back:', err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { mutate, isLoading, error };
}

export default useOptimisticMutation;
