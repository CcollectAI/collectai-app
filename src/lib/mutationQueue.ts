/**
 * Offline Mutation Queue
 *
 * Queues data mutations (create/update/delete) when the device is offline.
 * Replays them in FIFO order when connectivity is restored.
 * Persists the queue to AsyncStorage so queued mutations survive app restarts.
 *
 * Supported mutation types map 1:1 to DataProvider write methods.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

const QUEUE_KEY = 'collectai_mutation_queue';
const MAX_RETRIES = 3;

// ── Types ───────────────────────────────────────────────────────────────────

export type MutationType =
  | 'createItem'
  | 'updateItem'
  | 'deleteItem'
  | 'rsvpEvent'
  | 'unrsvpEvent'
  | 'sendMessage'
  | 'addWatchlistItem'
  | 'removeWatchlistItem'
  | 'removeWatchlistItems'
  | 'createEvent'
  | 'updateEvent'
  | 'deleteEvent'
  | 'cancelEvent'
  | 'updateWatchlistItem'
  | 'convertWatchlistToItem'
  | 'createBuildPaintProject'
  | 'updateBuildPaintProject'
  | 'setBuildPaintProgress'
  | 'markBuildPaintProjectComplete'
  | 'addBuildPaintStep'
  | 'toggleBuildPaintStep'
  | 'addBuildPaintNote'
  | 'submitFeedback'
  | 'submitCorrection'
  | 'toggleForSale'
  | 'archiveItem'
  | 'unarchiveItem'
  | 'markCategoryItemOwned'
  | 'followCategory'
  | 'unfollowCategory'
  | 'blockUser'
  | 'unblockUser'
  | 'requestDm'
  | 'decideDmRequest'
  | 'proposeOffer'
  | 'counterOffer'
  | 'respondToOffer'
  | 'cancelOffer'
  | 'markShipped'
  | 'completeDeal'
  | 'logActivity';

export type QueuedMutation = {
  id: string;
  type: MutationType;
  args: unknown[];
  createdAt: string;
  retries: number;
};

/** Callback invoked when mutations permanently fail after all retries. */
export type OnPermanentFailureCallback = (
  failed: { type: MutationType; id: string; createdAt: string }[],
) => void;

// ── Internal state ──────────────────────────────────────────────────────────

let _queue: QueuedMutation[] = [];
let _isReplaying = false;
let _onPermanentFailure: OnPermanentFailureCallback | null = null;

/**
 * Register a callback that fires when mutations permanently fail (after MAX_RETRIES).
 * Use this to show a toast or alert in the UI layer.
 */
export function setOnPermanentFailure(cb: OnPermanentFailureCallback | null): void {
  _onPermanentFailure = cb;
}

// ── Persistence ─────────────────────────────────────────────────────────────

/**
 * Load queue from persistent storage.
 * Call once at app startup before any mutations can be queued.
 */
export async function loadQueue(): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(QUEUE_KEY);
    _queue = raw ? JSON.parse(raw) : [];
    logger.info(`[MutationQueue] Loaded ${_queue.length} queued mutations`);
  } catch (e) {
    logger.error('[silent-catch] mutationQueue.ts:100:', e);
    _queue = [];
  }
}

/**
 * Save queue to persistent storage.
 */
async function persistQueue(): Promise<void> {
  try {
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(_queue));
  } catch {
    logger.error('[MutationQueue] Failed to persist queue');
  }
}

// ── Enqueue / dequeue ───────────────────────────────────────────────────────

/**
 * Enqueue a mutation for later replay.
 * Returns the generated mutation ID.
 */
export async function enqueueMutation(
  type: MutationType,
  ...args: unknown[]
): Promise<string> {
  const id = `mut_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const mutation: QueuedMutation = {
    id,
    type,
    args,
    createdAt: new Date().toISOString(),
    retries: 0,
  };
  _queue.push(mutation);
  await persistQueue();
  logger.info(`[MutationQueue] Enqueued ${type} (id=${id})`);
  return id;
}

/**
 * Remove a specific mutation from the queue by ID.
 */
export async function removeMutation(id: string): Promise<void> {
  _queue = _queue.filter((m) => m.id !== id);
  await persistQueue();
}

/**
 * Clear the entire queue.
 */
export async function clearQueue(): Promise<void> {
  _queue = [];
  await persistQueue();
}

// ── Accessors ───────────────────────────────────────────────────────────────

/** Get the current queue length (synchronous). */
export function getQueueLength(): number {
  return _queue.length;
}

/** Get a shallow copy of all queued mutations (for UI display). */
export function getQueuedMutations(): QueuedMutation[] {
  return [..._queue];
}

/** Check if the queue is currently replaying. */
export function isReplaying(): boolean {
  return _isReplaying;
}

// ── Replay ──────────────────────────────────────────────────────────────────

/**
 * Replay all queued mutations through the provided executor function.
 * Called when connectivity is restored.
 *
 * Mutations are executed in FIFO order. Failures are retried up to
 * MAX_RETRIES times before being permanently dropped.
 *
 * @param executor - async function that performs the actual mutation
 * @returns counts of succeeded and permanently-failed mutations
 */
export async function replayQueue(
  executor: (type: MutationType, args: unknown[]) => Promise<void>,
): Promise<{ succeeded: number; failed: number }> {
  if (_isReplaying || _queue.length === 0) {
    return { succeeded: 0, failed: 0 };
  }

  _isReplaying = true;
  let succeeded = 0;
  let failed = 0;
  const retryLater: QueuedMutation[] = [];
  const permanentlyFailed: { type: MutationType; id: string; createdAt: string }[] = [];

  logger.info(`[MutationQueue] Replaying ${_queue.length} mutations`);

  for (const mutation of _queue) {
    try {
      await executor(mutation.type, mutation.args);
      succeeded++;
      logger.info(`[MutationQueue] Replayed ${mutation.type} (id=${mutation.id})`);
    } catch (err) {
      mutation.retries++;
      if (mutation.retries < MAX_RETRIES) {
        retryLater.push(mutation);
        logger.error(
          `[MutationQueue] Failed ${mutation.type} (retry ${mutation.retries}/${MAX_RETRIES}): ${err}`,
        );
      } else {
        failed++;
        permanentlyFailed.push({
          type: mutation.type,
          id: mutation.id,
          createdAt: mutation.createdAt,
        });
        logger.error(
          `[MutationQueue] Permanently failed ${mutation.type} after ${MAX_RETRIES} retries`,
        );
      }
    }
  }

  _queue = retryLater;
  await persistQueue();
  _isReplaying = false;

  // Notify UI layer about permanent failures
  if (permanentlyFailed.length > 0 && _onPermanentFailure) {
    try {
      _onPermanentFailure(permanentlyFailed);
    } catch {
      logger.error('[MutationQueue] onPermanentFailure callback threw');
    }
  }

  logger.info(
    `[MutationQueue] Replay complete: ${succeeded} succeeded, ${failed} permanently failed, ${retryLater.length} will retry`,
  );
  return { succeeded, failed };
}
