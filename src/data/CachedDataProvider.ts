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
  AlertRule,
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
  Offer,
  OfferEvent,
  UserReputation,
} from './types';
import type { CollectorsEvent, CreateEventInput, EventTemplate, EventAnnouncement, SponsorCompany } from './events';
import { cacheGet, cacheSet, cacheClear } from './offlineCache';
import { followedCategoriesStore } from './followedCategoriesStore';
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
  CATEGORY_MISSING: 'category:missing',        // prefix — keyed per category
  EVENTS: 'events:list',
  EVENT_BY_ID: 'event:id',                      // prefix — keyed per event
  ANALYTICS: 'analytics:metrics',
  BUILD_PAINT_PROJECTS: 'buildpaint:projects',
  FOLLOWED_CATEGORIES: 'categories:followed',
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

  /**
   * Deliberately NOT cached. Rules mutate on direct user action (created from
   * the wishlist target-price flow, deleted by swiping on the Alerts screen),
   * and the Rules tab deletes optimistically then refreshes — an SWR copy
   * would hand back the row the user just removed. The list is small and
   * user-scoped, so the pass-through costs one cheap request.
   */
  listAlertRules(pagination?: PaginationParams): Promise<AlertRule[]> {
    return this.inner.listAlertRules(pagination);
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

  async updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>>): Promise<Item> {
    const result = await this.inner.updateItem(itemId, patch);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
    return result;
  }

  async archiveItem(itemId: string): Promise<void> {
    await this.inner.archiveItem(itemId);
    await Promise.all([
      cacheClear(CK.ITEMS_LIST),
      cacheClear(CK.PORTFOLIO_SUMMARY),
    ]);
  }

  async unarchiveItem(itemId: string): Promise<void> {
    await this.inner.unarchiveItem(itemId);
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

  async updateWatchlistItem(id: string, updates: { targetPrice?: number | null; notes?: string; sortOrder?: number }): Promise<WatchlistItem> {
    const result = await this.inner.updateWatchlistItem(id, updates);
    await cacheClear(CK.WATCHLIST);
    return result;
  }

  async removeWatchlistItem(id: string): Promise<void> {
    await this.inner.removeWatchlistItem(id);
    await cacheClear(CK.WATCHLIST);
  }

  async removeWatchlistItems(ids: string[]): Promise<void> {
    await this.inner.removeWatchlistItems(ids);
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

  // Must FORWARD the result, not swallow it: on a full event the server
  // downgrades 'going' to 'interested' and reports `waitlisted: true`, and the
  // caller has no other way to learn what was actually stored.
  async rsvpEvent(
    eventId: string,
    status?: 'going' | 'interested' | 'not_going',
  ): Promise<{ status: string; waitlisted: boolean }> {
    const result = await this.inner.rsvpEvent(eventId, status);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(`${CK.EVENT_BY_ID}:${eventId}`),
    ]);
    return result;
  }

  async unrsvpEvent(eventId: string): Promise<void> {
    await this.inner.unrsvpEvent(eventId);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(`${CK.EVENT_BY_ID}:${eventId}`),
    ]);
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
    await Promise.all([
      cacheClear(CK.CATEGORY_SUMMARIES),
      // Clear all category-missing caches (we don't know which category this item belongs to)
      cacheClear(CK.CATEGORY_MISSING),
    ]);
    return result;
  }

  async followCategory(categoryId: string): Promise<void> {
    await this.inner.followCategory(categoryId);
    // Propagate to every useFollowedCategories consumer immediately.
    followedCategoriesStore.add(categoryId);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(CK.CATEGORY_SUMMARIES),
      cacheClear(CK.FOLLOWED_CATEGORIES),
    ]);
  }

  async unfollowCategory(categoryId: string): Promise<void> {
    await this.inner.unfollowCategory(categoryId);
    followedCategoriesStore.remove(categoryId);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(CK.CATEGORY_SUMMARIES),
      cacheClear(CK.FOLLOWED_CATEGORIES),
    ]);
  }

  // ── Pass-through reads (not cached — too dynamic or user-scoped) ────────

  searchItems(query: string): Promise<Item[]> {
    return this.inner.searchItems(query);
  }

  quickscanSingle(imageUri?: string): Promise<QuickScanResult> {
    return this.inner.quickscanSingle(imageUri);
  }

  getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
    return swr(`profile:${userId}`, () => this.inner.getPublicUserProfile(userId), TTL_SHORT);
  }

  getMyProfile(): Promise<PublicUserProfile | null> {
    return this.inner.getMyProfile();
  }

  getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
    return swr(`category:store:${categoryId}`, () => this.inner.getCategoryStore(categoryId), TTL_MEDIUM);
  }

  listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
    return swr(
      `${CK.CATEGORY_MISSING}:${categoryId}`,
      () => this.inner.listCategoryMissing(categoryId),
      TTL_MEDIUM,
    );
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

  setTyping(threadId: string): Promise<void> {
    return this.inner.setTyping(threadId);
  }

  clearTyping(threadId: string): Promise<void> {
    return this.inner.clearTyping(threadId);
  }

  isOtherUserTyping(threadId: string): Promise<boolean> {
    return this.inner.isOtherUserTyping(threadId);
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

  listBuildPaintProjectsByCategory(categoryId: string): Promise<BuildPaintProject[]> {
    return this.inner.listBuildPaintProjectsByCategory(categoryId);
  }

  listBuildPaintProjectsByItem(itemId: string): Promise<BuildPaintProject[]> {
    return this.inner.listBuildPaintProjectsByItem(itemId);
  }

  async applyStepTemplate(projectId: string, categoryId: string): Promise<BuildPaintStep[]> {
    const result = await this.inner.applyStepTemplate(projectId, categoryId);
    await cacheClear(CK.BUILD_PAINT_PROJECTS);
    return result;
  }

  async updateBuildPaintProject(projectId: string, patch: { paintRecipes?: unknown[] }): Promise<void> {
    await this.inner.updateBuildPaintProject(projectId, patch);
    await cacheClear(CK.BUILD_PAINT_PROJECTS);
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

  // Category following — cached (lightweight RPCs, rarely change)
  listFollowedCategories(): Promise<string[]> {
    return swr(CK.FOLLOWED_CATEGORIES, () => this.inner.listFollowedCategories(), TTL_MEDIUM);
  }

  isFollowingCategory(categoryId: string): Promise<boolean> {
    return this.inner.isFollowingCategory(categoryId);
  }

  // Events — single item lookup (cached). TTL_LONG because event rows rarely
  // change and SWR revalidates in the background on every open anyway; a long
  // TTL keeps re-opens instant. First open is primed via primeEventCache()
  // from the list so the detail screen skips its blocking skeleton entirely.
  getEventById(eventId: string): Promise<CollectorsEvent | null> {
    return swr(
      `${CK.EVENT_BY_ID}:${eventId}`,
      () => this.inner.getEventById(eventId),
      TTL_LONG,
    );
  }

  shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
    return this.inner.shareEventViaDm(eventId, recipientUserId);
  }

  // User search — pass through (dynamic query results)
  searchUsers(query: string): Promise<PublicUserProfile[]> {
    return this.inner.searchUsers(query);
  }

  // User blocking — pass through (mutations, not cacheable)
  blockUser(userId: string): Promise<void> {
    return this.inner.blockUser(userId);
  }

  unblockUser(userId: string): Promise<void> {
    return this.inner.unblockUser(userId);
  }

  listBlockedUsers(): Promise<{ id: string; name: string }[]> {
    return this.inner.listBlockedUsers();
  }

  isBlocked(userId: string): Promise<boolean> {
    return this.inner.isBlocked(userId);
  }

  // Events — host actions (mutations, pass through with cache invalidation)
  async updateEvent(eventId: string, patch: Partial<CreateEventInput & { status?: string }>): Promise<CollectorsEvent> {
    const result = await this.inner.updateEvent(eventId, patch);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(`${CK.EVENT_BY_ID}:${eventId}`),
    ]);
    return result;
  }

  async cancelEvent(eventId: string): Promise<void> {
    await this.inner.cancelEvent(eventId);
    await Promise.all([
      cacheClear(CK.EVENTS),
      cacheClear(`${CK.EVENT_BY_ID}:${eventId}`),
    ]);
  }

  async duplicateEvent(eventId: string): Promise<CollectorsEvent> {
    const result = await this.inner.duplicateEvent(eventId);
    await cacheClear(CK.EVENTS);
    return result;
  }

  // Event templates — pass through
  listEventTemplates(): Promise<EventTemplate[]> {
    return this.inner.listEventTemplates();
  }

  createEventTemplate(name: string, fromEventId?: string): Promise<EventTemplate> {
    return this.inner.createEventTemplate(name, fromEventId);
  }

  deleteEventTemplate(templateId: string): Promise<void> {
    return this.inner.deleteEventTemplate(templateId);
  }

  // Sponsor companies — pass through
  registerSponsorCompany(input: { name: string; logoUrl?: string; websiteUrl?: string; contactEmail: string; description?: string }): Promise<SponsorCompany> {
    return this.inner.registerSponsorCompany(input);
  }

  getMySponsorCompanies(): Promise<SponsorCompany[]> {
    return this.inner.getMySponsorCompanies();
  }

  updateSponsorCompany(id: string, patch: Partial<{ name: string; logoUrl: string; websiteUrl: string; contactEmail: string; description: string }>): Promise<SponsorCompany> {
    return this.inner.updateSponsorCompany(id, patch);
  }

  createSponsorEventCheckout(companyId: string, tier: string, eventData: CreateEventInput): Promise<{ url: string; sessionId: string; eventId: string }> {
    return this.inner.createSponsorEventCheckout(companyId, tier, eventData);
  }

  createTicketCheckout(eventId: string): Promise<{ url: string; sessionId: string }> {
    return this.inner.createTicketCheckout(eventId);
  }

  createSponsorSubscriptionCheckout(companyId: string, tier: string): Promise<{ url: string; sessionId: string }> {
    return this.inner.createSponsorSubscriptionCheckout(companyId, tier);
  }

  // Event announcements — pass through (real-time)
  listEventAnnouncements(eventId: string): Promise<EventAnnouncement[]> {
    return this.inner.listEventAnnouncements(eventId);
  }

  postEventAnnouncement(eventId: string, body: string, title?: string, imageUrl?: string): Promise<EventAnnouncement> {
    return this.inner.postEventAnnouncement(eventId, body, title, imageUrl);
  }

  markAnnouncementRead(eventId: string, announcementId: string): Promise<void> {
    return this.inner.markAnnouncementRead(eventId, announcementId);
  }

  getUnreadAnnouncementCount(): Promise<number> {
    return this.inner.getUnreadAnnouncementCount();
  }

  // Category deep dive — cached (market aggregates change slowly; the backend
  // also caches this, but SWR keeps re-opens instant instead of paying a
  // round-trip + heavy market_hits scan every time the category opens).
  getCategoryDeepDive(categoryId: string, days?: number): Promise<Record<string, unknown>> {
    return swr(
      `category:deepdive:${categoryId}:${days ?? 'def'}`,
      () => this.inner.getCategoryDeepDive(categoryId, days),
      TTL_LONG,
    );
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

  // Presence — pass through (real-time)
  sendHeartbeat(): Promise<void> { return this.inner.sendHeartbeat(); }
  goOffline(): Promise<void> { return this.inner.goOffline(); }
  getUserPresence(userId: string) { return this.inner.getUserPresence(userId); }
  getBatchPresence(userIds: string[]) { return this.inner.getBatchPresence(userIds); }

  // Activity feed — pass through
  getUserActivity(userId: string, limit?: number, offset?: number) { return this.inner.getUserActivity(userId, limit, offset); }
  logActivity(activityType: string, title: string, description?: string, metadata?: Record<string, unknown>, isPublic?: boolean) { return this.inner.logActivity(activityType, title, description, metadata, isPublic); }

  // Unified search — pass through
  unifiedSearch(query: string, limit?: number) { return this.inner.unifiedSearch(query, limit); }

  // Event search — pass through
  searchEvents(params: { q?: string; category?: string; eventType?: string; location?: string; upcomingOnly?: boolean; limit?: number; offset?: number }) { return this.inner.searchEvents(params); }

  // Deal Desk (P2P Offers) — mutations invalidate items cache
  async proposeOffer(itemId: string, price: number, message?: string): Promise<Offer> {
    const result = await this.inner.proposeOffer(itemId, price, message);
    return result;
  }
  async counterOffer(offerId: string, price: number, message?: string): Promise<Offer> {
    const result = await this.inner.counterOffer(offerId, price, message);
    return result;
  }
  async respondToOffer(offerId: string, accept: boolean, message?: string): Promise<void> {
    await this.inner.respondToOffer(offerId, accept, message);
    // Accepting removes item from sale — invalidate items
    if (accept) await cacheClear(CK.ITEMS_LIST);
  }
  cancelOffer(offerId: string): Promise<void> { return this.inner.cancelOffer(offerId); }
  listActiveOffers(): Promise<Offer[]> { return this.inner.listActiveOffers(); }
  listDealHistory(): Promise<Offer[]> { return this.inner.listDealHistory(); }
  getOfferDetail(offerId: string): Promise<{ offer: Offer; events: OfferEvent[] }> { return this.inner.getOfferDetail(offerId); }
  getUserReputation(userId: string): Promise<UserReputation> { return this.inner.getUserReputation(userId); }
  async toggleForSale(itemId: string, forSale: boolean, askingPrice?: number): Promise<void> {
    await this.inner.toggleForSale(itemId, forSale, askingPrice);
    await cacheClear(CK.ITEMS_LIST);
  }
  markShipped(offerId: string, trackingInfo?: string): Promise<void> { return this.inner.markShipped(offerId, trackingInfo); }
  async completeDeal(offerId: string, stars: number, comment?: string): Promise<void> {
    await this.inner.completeDeal(offerId, stars, comment);
    await cacheClear(CK.ITEMS_LIST);
  }

  // Multi-Marketplace Selling (pass-through)
  listMarketplaceListings(status?: import('./types').MarketplaceListing['status']): Promise<import('./types').MarketplaceListing[]> { return this.inner.listMarketplaceListings(status); }
  createMarketplaceListing(input: Omit<import('./types').MarketplaceListing, 'id' | 'viewsCount' | 'watchersCount' | 'offersCount' | 'createdAt'>): Promise<import('./types').MarketplaceListing> { return this.inner.createMarketplaceListing(input); }
  updateMarketplaceListing(listingId: string, patch: Partial<import('./types').MarketplaceListing>): Promise<import('./types').MarketplaceListing> { return this.inner.updateMarketplaceListing(listingId, patch); }
  deleteMarketplaceListing(listingId: string): Promise<void> { return this.inner.deleteMarketplaceListing(listingId); }
  listMarketplaceAccounts(): Promise<import('./types').MarketplaceAccount[]> { return this.inner.listMarketplaceAccounts(); }
  listMarketplaceSales(): Promise<import('./types').MarketplaceSale[]> { return this.inner.listMarketplaceSales(); }
  getMarketplaceFeeSchedules(): Promise<import('./types').MarketplaceFeeSchedule[]> { return this.inner.getMarketplaceFeeSchedules(); }
}

/**
 * Seed the event-detail cache with an event the caller already holds (e.g. the
 * events list row that was just tapped). The detail screen's getEventById then
 * hits this cached value immediately and renders without its blocking
 * skeleton, while SWR revalidates the authoritative row in the background.
 * Fire-and-forget; safe to call regardless of which provider is active.
 */
export function primeEventCache(event: CollectorsEvent): void {
  if (!event?.id) return;
  void cacheSet(`${CK.EVENT_BY_ID}:${event.id}`, event, TTL_LONG).catch((err) =>
    logger.warn('[CachedDataProvider] primeEventCache failed:', err),
  );
}
