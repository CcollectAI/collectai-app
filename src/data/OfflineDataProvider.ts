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

// ── Mutation executor ───────────────────────────────────────────────────────

/**
 * Execute a single mutation against the real DataProvider by type.
 * This is the replay callback passed to `replayQueue()`.
 */
async function executeMutation(type: MutationType, args: unknown[]): Promise<void> {
  switch (type) {
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
    case 'rsvpEvent':
      await dataProvider.rsvpEvent(args[0] as string, args[1] as string);
      break;
    case 'sendMessage':
      await dataProvider.sendMessage(args[0] as string, args[1] as string);
      break;
    case 'addWatchlistItem':
      await dataProvider.addWatchlistItem(
        args[0] as Parameters<typeof dataProvider.addWatchlistItem>[0],
      );
      break;
    case 'removeWatchlistItem':
      await dataProvider.removeWatchlistItem(args[0] as string);
      break;
    case 'createEvent':
      await dataProvider.createEvent(args[0] as Parameters<typeof dataProvider.createEvent>[0]);
      break;
    case 'updateWatchlistItem':
      await dataProvider.updateWatchlistItem(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateWatchlistItem>[1],
      );
      break;
    case 'createBuildPaintProject':
      await dataProvider.createBuildPaintProject(
        args[0] as Parameters<typeof dataProvider.createBuildPaintProject>[0],
      );
      break;
    case 'deleteEvent':
      await collectorsApi.deleteEvent(args[0] as string);
      break;
    case 'updateEvent':
      await dataProvider.updateEvent(
        args[0] as string,
        args[1] as Parameters<typeof dataProvider.updateEvent>[1],
      );
      break;
    case 'submitFeedback':
      await dataProvider.submitFeedback(
        args[0] as string,
        args[1] as 'sale_price' | 'disagree' | 'accurate',
        args[2] as string | undefined,
      );
      break;
    case 'toggleForSale':
      await dataProvider.toggleForSale(
        args[0] as string,
        args[1] as boolean,
        args[2] as number | undefined,
      );
      break;
    case 'archiveItem':
      await dataProvider.archiveItem(args[0] as string);
      break;
    case 'unarchiveItem':
      await dataProvider.unarchiveItem(args[0] as string);
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
