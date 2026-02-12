/**
 * CachedDataProvider — transparent cache wrapper around any DataProvider.
 *
 * Uses the SQLite offlineCache for stale-while-revalidate semantics:
 *   1. Return cached data immediately (even if stale).
 *   2. Fire a background fetch to refresh the cache.
 *   3. On mutation (create/delete/archive), invalidate affected cache keys.
 *
 * Methods that are NOT cached pass straight through to the inner provider.
 */

import type { DataProvider } from './DataProvider';
import type {
  PaginationParams,
  PortfolioSummary,
  Item,
  WatchlistItem,
  CreateItemInput,
  CreateWatchlistInput,
  QuickScanResult,
  QuickscanDraft,
  PersistedItem,
  PublicUserProfile,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
  AlertFeedItem,
  DmThread,
  DmRequest,
  DmMessage,
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  CreateBuildPaintProjectInput,
  BarcodeLookupResult,
  MarketSearchOptions,
  MarketSearchResult,
} from './types';
import type { CollectorsEvent, CreateEventInput } from './events';
import { cacheGet, cacheSet, cacheClear } from './offlineCache';
import logger from '../utils/logger';

// ---------------------------------------------------------------------------
// Cache key constants
// ---------------------------------------------------------------------------

const CK = {
  ITEMS_LIST: 'items:list',
  PORTFOLIO_SUMMARY: 'portfolio:summary',
  WATCHLIST: 'watchlist:list',
  ALERTS_FEED: 'alerts:feed',
  CATEGORY_SUMMARIES: 'categories:summaries',
  EVENTS: 'events:list',
  ANALYTICS: 'analytics:metrics',
  BUILD_PAINT_PROJECTS: 'buildpaint:projects',
} as const;

// Default TTLs (milliseconds)
const TTL_SHORT = 2 * 60 * 1000;   // 2 minutes  — portfolio, watchlist
const TTL_MEDIUM = 5 * 60 * 1000;  // 5 minutes  — items, alerts
const TTL_LONG = 15 * 60 * 1000;   // 15 minutes — categories, events

// ---------------------------------------------------------------------------
// Helper — stale-while-revalidate
// ---------------------------------------------------------------------------

/**
 * Returns cached data immediately.  If the cache misses, waits for the
 * network fetch.  If the cache hits, a background revalidation still runs
 * to keep the data fresh.
 */
async function swr<T>(
  cacheKey: string,
  fetcher: () => Promise<T>,
  ttlMs: number,
): Promise<T> {
  const cached = await cacheGet<T>(cacheKey);

  if (cached !== null) {
    // Revalidate in the background — fire and forget
    fetcher()
      .then((fresh) => cacheSet(cacheKey, fresh, ttlMs))
      .catch((err) => logger.warn(`[CachedDataProvider] bg revalidate ${cacheKey}:`, err));

    return cached;
  }

  // No cached value — must fetch
  const fresh = await fetcher();
  await cacheSet(cacheKey, fresh, ttlMs);
  return fresh;
}

// ---------------------------------------------------------------------------
// CachedDataProvider
// ---------------------------------------------------------------------------

export class CachedDataProvider implements DataProvider {
  constructor(private inner: DataProvider) {}

  // ── Cached reads (stale-while-revalidate) ───────────────────────────────

  getPortfolioSummary(): Promise<PortfolioSummary> {
    return swr(CK.PORTFOLIO_SUMMARY, () => this.inner.getPortfolioSummary(), TTL_SHORT);
  }

  listItems(pagination?: PaginationParams): Promise<Item[]> {
    // Skip cache for paginated requests beyond the first page
    if (pagination && (pagination.offset ?? 0) > 0) {
      return this.inner.listItems(pagination);
    }
    return swr(CK.ITEMS_LIST, () => this.inner.listItems(pagination), TTL_MEDIUM);
  }

  listWatchlist(userId: string): Promise<WatchlistItem[]> {
    return swr(CK.WATCHLIST, () => this.inner.listWatchlist(userId), TTL_SHORT);
  }

  listAlertsFeed(pagination?: PaginationParams): Promise<AlertFeedItem[]> {
    if (pagination && (pagination.offset ?? 0) > 0) {
      return this.inner.listAlertsFeed(pagination);
    }
    return swr(CK.ALERTS_FEED, () => this.inner.listAlertsFeed(pagination), TTL_MEDIUM);
  }

  listCategorySummaries(): Promise<CategorySummary[]> {
    return swr(CK.CATEGORY_SUMMARIES, () => this.inner.listCategorySummaries(), TTL_LONG);
  }

  listEvents(pagination?: PaginationParams): Promise<CollectorsEvent[]> {
    if (pagination && (pagination.offset ?? 0) > 0) {
      return this.inner.listEvents(pagination);
    }
    return swr(CK.EVENTS, () => this.inner.listEvents(pagination), TTL_LONG);
  }

  getAnalyticsMetrics(): Promise<AnalyticsMetrics> {
    return swr(CK.ANALYTICS, () => this.inner.getAnalyticsMetrics(), TTL_SHORT);
  }

  listBuildPaintProjects(): Promise<BuildPaintProject[]> {
    return swr(CK.BUILD_PAINT_PROJECTS, () => this.inner.listBuildPaintProjects(), TTL_MEDIUM);
  }

  // ── Mutations with cache invalidation ───────────────────────────────────

  async createItem(input: CreateItemInput): Promise<Item> {
    const result = await this.inner.createItem(input);
    // Invalidate items list and portfolio (counts/values change)
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
    return result;
  }

  async deleteItem(itemId: string): Promise<void> {
    await this.inner.deleteItem(itemId);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
  }

  async archiveItem(itemId: string): Promise<void> {
    await this.inner.archiveItem(itemId);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
  }

  async addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
    const result = await this.inner.addWatchlistItem(input);
    await cacheClear(CK.WATCHLIST);
    return result;
  }

  async removeWatchlistItem(id: string): Promise<void> {
    await this.inner.removeWatchlistItem(id);
    await cacheClear(CK.WATCHLIST);
  }

  async convertWatchlistToItem(
    watchlistItemId: string,
    actualPrice?: number,
    notes?: string,
  ): Promise<Item> {
    const result = await this.inner.convertWatchlistToItem(watchlistItemId, actualPrice, notes);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
      cacheClear(CK.WATCHLIST),
    ]);
    return result;
  }

  async persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
    const result = await this.inner.persistQuickscanDraft(input);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
    return result;
  }

  async createEvent(input: CreateEventInput): Promise<CollectorsEvent> {
    const result = await this.inner.createEvent(input);
    await cacheClear(CK.EVENTS);
    return result;
  }

  async rsvpEvent(eventId: string, status?: string): Promise<void> {
    await this.inner.rsvpEvent(eventId, status);
    await cacheClear(CK.EVENTS);
  }

  async unrsvpEvent(eventId: string): Promise<void> {
    await this.inner.unrsvpEvent(eventId);
    await cacheClear(CK.EVENTS);
  }

  async createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
    const result = await this.inner.createBuildPaintProject(input);
    await Promise.all([
      cacheClear(CK.BUILD_PAINT_PROJECTS),
      cacheClear(CK.ANALYTICS),
    ]);
    return result;
  }

  async setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
    await this.inner.setBuildPaintProgress(projectId, percent, status);
    await cacheClear(CK.BUILD_PAINT_PROJECTS);
  }

  async markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
    await this.inner.markBuildPaintProjectComplete(projectId, isCompleted);
    await Promise.all([
      cacheClear(CK.BUILD_PAINT_PROJECTS),
      cacheClear(CK.ANALYTICS),
    ]);
  }

  async markCategoryItemOwned(
    categoryItemId: string,
    quantity?: number,
    notes?: string,
  ): Promise<{ success: boolean }> {
    const result = await this.inner.markCategoryItemOwned(categoryItemId, quantity, notes);
    await cacheClear(CK.CATEGORY_SUMMARIES);
    return result;
  }

  async followCategory(categoryId: string): Promise<void> {
    await this.inner.followCategory(categoryId);
    await cacheClear(CK.EVENTS);
  }

  async unfollowCategory(categoryId: string): Promise<void> {
    await this.inner.unfollowCategory(categoryId);
    await cacheClear(CK.EVENTS);
  }

  // ── Pass-through reads (not cached — too dynamic or user-scoped) ────────

  searchItems(query: string): Promise<Item[]> {
    return this.inner.searchItems(query);
  }

  quickscanSingle(): Promise<QuickScanResult> {
    return this.inner.quickscanSingle();
  }

  getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
    return this.inner.getPublicUserProfile(userId);
  }

  getMyProfile(): Promise<PublicUserProfile | null> {
    return this.inner.getMyProfile();
  }

  getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
    return this.inner.getCategoryStore(categoryId);
  }

  listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
    return this.inner.listCategoryMissing(categoryId);
  }

  // DM / inbox — real-time, not cached
  listInboxThreads(): Promise<DmThread[]> {
    return this.inner.listInboxThreads();
  }

  listIncomingRequests(): Promise<DmRequest[]> {
    return this.inner.listIncomingRequests();
  }

  requestDm(toUserId: string, message?: string): Promise<string> {
    return this.inner.requestDm(toUserId, message);
  }

  decideDmRequest(threadId: string, accept: boolean): Promise<void> {
    return this.inner.decideDmRequest(threadId, accept);
  }

  markThreadRead(threadId: string): Promise<void> {
    return this.inner.markThreadRead(threadId);
  }

  getThreadMessages(threadId: string): Promise<DmMessage[]> {
    return this.inner.getThreadMessages(threadId);
  }

  sendMessage(threadId: string, body: string): Promise<DmMessage> {
    return this.inner.sendMessage(threadId, body);
  }

  getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> {
    return this.inner.getDmStatus(otherUserId);
  }

  getInboxUnreadCount(): Promise<number> {
    return this.inner.getInboxUnreadCount();
  }

  // Build & paint — sub-resources pass through
  listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]> {
    return this.inner.listBuildPaintSteps(projectId);
  }

  addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep> {
    return this.inner.addBuildPaintStep(projectId, title);
  }

  toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void> {
    return this.inner.toggleBuildPaintStep(stepId, isDone);
  }

  listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]> {
    return this.inner.listBuildPaintNotes(projectId);
  }

  addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote> {
    return this.inner.addBuildPaintNote(projectId, body);
  }

  // Feedback — pass through
  submitFeedback(
    itemId: string,
    feedbackType: 'sale_price' | 'disagree' | 'accurate',
    value?: string,
  ): Promise<{ success: boolean; feedbackId?: string }> {
    return this.inner.submitFeedback(itemId, feedbackType, value);
  }

  submitCorrection(
    itemId: string,
    corrections: {
      correctedPrice?: number;
      correctedCondition?: string;
      correctedCategory?: string;
      notes?: string;
    },
  ): Promise<{ success: boolean }> {
    return this.inner.submitCorrection(itemId, corrections);
  }

  // Category following — pass through (lightweight RPCs)
  listFollowedCategories(): Promise<string[]> {
    return this.inner.listFollowedCategories();
  }

  isFollowingCategory(categoryId: string): Promise<boolean> {
    return this.inner.isFollowingCategory(categoryId);
  }

  // Events — single item lookup pass through
  getEventById(eventId: string): Promise<CollectorsEvent | null> {
    return this.inner.getEventById(eventId);
  }

  shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
    return this.inner.shareEventViaDm(eventId, recipientUserId);
  }

  // Barcode / market — pass through (results vary per query)
  lookupByBarcode(
    barcode: string,
    opts?: { codeType?: string },
  ): Promise<BarcodeLookupResult> {
    return this.inner.lookupByBarcode(barcode, opts);
  }

  marketSearch(
    query: string,
    opts?: MarketSearchOptions,
  ): Promise<MarketSearchResult> {
    return this.inner.marketSearch(query, opts);
  }
}
