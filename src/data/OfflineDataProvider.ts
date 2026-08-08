/**
 * OfflineDataProvider — initialises the offline mutation queue and
 * provides the `offlineSafeMutation()` helper.
 *
 * When the device is online, mutations are executed immediately through the
 * active DataProvider.  When offline, they are enqueued in the persistent
 * mutation queue and replayed automatically once connectivity is restored.
 *
 * Call `initOfflineQueue()` once at app startup (e.g. in root layout).
 */

import { dataProvider } from '@/data';
import { collectorsApi } from '@/api/collectorsApi';
import {
  enqueueMutation,
  replayQueue,
  loadQueue,
  getQueueLength,
  setOnPermanentFailure,
  type MutationType,
} from '@/lib/mutationQueue';
import { onReconnect, isDeviceOnline } from '@/hooks/useNetworkStatus';
import logger from '@/utils/logger';

let _initialized = false;

// ── Initialisation ──────────────────────────────────────────────────────────

/**
 * Initialise the offline queue system.
 * - Loads any persisted queued mutations from AsyncStorage.
 * - Registers a reconnection listener so the queue auto-replays.
 * - If the device is already online and the queue is non-empty, replays now.
 *
 * Safe to call multiple times (idempotent).
 */
export async function initOfflineQueue(): Promise<void> {
  if (_initialized) return;
  _initialized = true;

  // Load persisted queue
  await loadQueue();

  // Register permanent-failure callback so the UI layer can be notified
  setOnPermanentFailure((failed) => {
    const types = failed.map((f) => f.type).join(', ');
    logger.error(
      `[OfflineQueue] ${failed.length} mutation(s) permanently failed: ${types}`,
    );
    // Notify registered listeners (e.g. Toast provider)
    for (const listener of _failureListeners) {
      try {
        listener(failed);
      } catch (e) {
        logger.error('[silent-catch] OfflineDataProvider.ts:54:', e);
        // swallow listener errors
      }
    }
  });

  // Auto-replay on reconnection
  onReconnect(async (connected) => {
    if (connected && getQueueLength() > 0) {
      logger.info('[OfflineQueue] Reconnected — replaying queued mutations');
      const result = await replayQueue(executeMutation);
      if (result.succeeded > 0) {
        logger.info(`[OfflineQueue] Replayed ${result.succeeded} mutations`);
      }
    }
  });

  // If we already have queued mutations and are online, replay immediately
  const online = await isDeviceOnline();
  if (online && getQueueLength() > 0) {
    const result = await replayQueue(executeMutation);
    if (result.succeeded > 0) {
      logger.info(`[OfflineQueue] Startup replay: ${result.succeeded} mutations`);
    }
  }
}

// ── Failure notification ─────────────────────────────────────────────────────

type FailureListener = (
  failed: { type: MutationType; id: string; createdAt: string }[],
) => void;
const _failureListeners: FailureListener[] = [];

/**
 * Register a listener that fires when queued mutations permanently fail.
 * Returns an unsubscribe function.
 *
 * Usage (e.g. in a React component or root layout):
 * ```ts
 * useEffect(() => {
 *   return onOfflineMutationFailure((failed) => {
 *     showToast(`${failed.length} offline change(s) could not be synced`);
 *   });
 * }, []);
 * ```
 */
export function onOfflineMutationFailure(listener: FailureListener): () => void {
  _failureListeners.push(listener);
  return () => {
    const idx = _failureListeners.indexOf(listener);
    if (idx >= 0) _failureListeners.splice(idx, 1);
  };
}

// ── Mutation executor ───────────────────────────────────────────────────────

/**
 * Execute a single mutation against the real DataProvider by type.
 * This is the replay callback passed to `replayQueue()`.
 */
async function executeMutation(type: MutationType, args: unknown[]): Promise<void> {
  switch (type) {
    // ── Item CRUD ──────────────────────────────────────────────────────────
    case 'createItem':
      await dataProvider.createItem(args[0] as Parameters<typeof dataProvider.createItem>[0]);
      break;
    case 'updateItem':
      await dataProvider.updateItem(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateItem>[1],
      );
      break;
    case 'deleteItem':
      await dataProvider.deleteItem(args[0] as string);
      break;
    case 'archiveItem':
      await dataProvider.archiveItem(args[0] as string);
      break;
    case 'unarchiveItem':
      await dataProvider.unarchiveItem(args[0] as string);
      break;
    case 'toggleForSale':
      await dataProvider.toggleForSale(
        args[0] as string,
        args[1] as boolean,
        args[2] as number | undefined,
      );
      break;

    // ── Events ─────────────────────────────────────────────────────────────
    case 'rsvpEvent':
      await dataProvider.rsvpEvent(
        args[0] as string,
        args[1] as 'going' | 'interested' | 'not_going' | undefined,
      );
      break;
    case 'unrsvpEvent':
      await dataProvider.unrsvpEvent(args[0] as string);
      break;
    case 'createEvent':
      await dataProvider.createEvent(args[0] as Parameters<typeof dataProvider.createEvent>[0]);
      break;
    case 'updateEvent':
      await dataProvider.updateEvent(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateEvent>[1],
      );
      break;
    case 'deleteEvent':
      await collectorsApi.deleteEvent(args[0] as string);
      break;
    case 'cancelEvent':
      await dataProvider.cancelEvent(args[0] as string);
      break;

    // ── Watchlist ──────────────────────────────────────────────────────────
    case 'addWatchlistItem':
      await dataProvider.addWatchlistItem(
        args[0] as Parameters<typeof dataProvider.addWatchlistItem>[0],
      );
      break;
    case 'removeWatchlistItem':
      await dataProvider.removeWatchlistItem(args[0] as string);
      break;
    case 'removeWatchlistItems':
      await dataProvider.removeWatchlistItems(args[0] as string[]);
      break;
    case 'updateWatchlistItem':
      await dataProvider.updateWatchlistItem(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateWatchlistItem>[1],
      );
      break;
    case 'convertWatchlistToItem':
      await dataProvider.convertWatchlistToItem(
        args[0] as string,
        args[1] as number | undefined,
        args[2] as string | undefined,
      );
      break;

    // ── Build & Paint ──────────────────────────────────────────────────────
    case 'createBuildPaintProject':
      await dataProvider.createBuildPaintProject(
        args[0] as Parameters<typeof dataProvider.createBuildPaintProject>[0],
      );
      break;
    case 'updateBuildPaintProject':
      await dataProvider.updateBuildPaintProject(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateBuildPaintProject>[1],
      );
      break;
    case 'setBuildPaintProgress':
      await dataProvider.setBuildPaintProgress(
        args[0] as string,
        args[1] as number,
        args[2] as string | undefined,
      );
      break;
    case 'markBuildPaintProjectComplete':
      await dataProvider.markBuildPaintProjectComplete(
        args[0] as string,
        args[1] as boolean,
      );
      break;
    case 'addBuildPaintStep':
      await dataProvider.addBuildPaintStep(args[0] as string, args[1] as string);
      break;
    case 'toggleBuildPaintStep':
      await dataProvider.toggleBuildPaintStep(args[0] as string, args[1] as boolean);
      break;
    case 'addBuildPaintNote':
      await dataProvider.addBuildPaintNote(args[0] as string, args[1] as string);
      break;

    // ── Feedback & Corrections ─────────────────────────────────────────────
    case 'submitFeedback':
      await dataProvider.submitFeedback(
        args[0] as string,
        args[1] as 'sale_price' | 'disagree' | 'accurate',
        args[2] as string | undefined,
      );
      break;
    case 'submitCorrection':
      await dataProvider.submitCorrection(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.submitCorrection>[1],
      );
      break;

    // ── Category Ownership & Following ─────────────────────────────────────
    case 'markCategoryItemOwned':
      await dataProvider.markCategoryItemOwned(
        args[0] as string,
        args[1] as number | undefined,
        args[2] as string | undefined,
      );
      break;
    case 'followCategory':
      await dataProvider.followCategory(args[0] as string);
      break;
    case 'unfollowCategory':
      await dataProvider.unfollowCategory(args[0] as string);
      break;

    // ── User Blocking ──────────────────────────────────────────────────────
    case 'blockUser':
      await dataProvider.blockUser(args[0] as string);
      break;
    case 'unblockUser':
      await dataProvider.unblockUser(args[0] as string);
      break;

    // ── Chat / DM ──────────────────────────────────────────────────────────
    case 'sendMessage':
      await dataProvider.sendMessage(args[0] as string, args[1] as string);
      break;
    case 'requestDm':
      await dataProvider.requestDm(args[0] as string, args[1] as string | undefined);
      break;
    case 'decideDmRequest':
      await dataProvider.decideDmRequest(args[0] as string, args[1] as boolean);
      break;

    // Deal Desk offer mutations removed 2026-08-09. A queued entry of one of
    // those kinds can only exist on a device that used a build where Deal Desk
    // was reachable — it never was (SELLING_ENABLED=false) — and the `default`
    // branch below degrades an unknown kind to a warning, not a crash.

    // ── Activity ───────────────────────────────────────────────────────────
    case 'logActivity':
      await dataProvider.logActivity(
        args[0] as string,
        args[1] as string,
        args[2] as string | undefined,
        args[3] as Record<string, unknown> | undefined,
        args[4] as boolean | undefined,
      );
      break;

    default:
      logger.warn(`[OfflineQueue] Unknown mutation type: ${type}`);
  }
}

// ── Public helper ───────────────────────────────────────────────────────────

/**
 * Try to execute a mutation online.  If the device is offline, queue it
 * for later replay instead.
 *
 * @returns `{ queued: false }` if executed immediately, or
 *          `{ queued: true, id }` with the queue entry ID if deferred.
 */
export async function offlineSafeMutation(
  type: MutationType,
  ...args: unknown[]
): Promise<{ queued: boolean; id?: string }> {
  const online = await isDeviceOnline();

  if (online) {
    // Online — execute directly (caller should handle errors)
    await executeMutation(type, args);
    return { queued: false };
  }

  // Offline — queue for later
  const id = await enqueueMutation(type, ...args);
  return { queued: true, id };
}
