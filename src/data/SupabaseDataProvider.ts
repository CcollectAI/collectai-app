/**
 * SupabaseDataProvider — fetches real data from Supabase.
 *
 * This class delegates to domain-specific provider modules in ./providers/.
 * It implements the DataProvider interface and is the single entry point
 * for all Supabase-backed data access.
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

// Domain providers
import * as portfolioProvider from './providers/portfolioProvider';
import * as itemsProvider from './providers/itemsProvider';
import * as watchlistProvider from './providers/watchlistProvider';
import * as categoryProvider from './providers/categoryProvider';
import * as chatProvider from './providers/chatProvider';
import * as userProvider from './providers/userProvider';
import * as eventsProvider from './providers/eventsProvider';
import * as buildPaintProvider from './providers/buildPaintProvider';
import * as feedbackProvider from './providers/feedbackProvider';
import * as marketProvider from './providers/marketProvider';
import * as presenceProvider from './providers/presenceProvider';
import * as activityProvider from './providers/activityProvider';
import * as dealsProvider from './providers/dealsProvider';

export class SupabaseDataProvider implements DataProvider {

  // ─── Portfolio ───────────────────────────────────────────────────────────────
  getPortfolioSummary = portfolioProvider.getPortfolioSummary;

  // ─── Items ──────────────────────────────────────────────────────────────────
  listItems = itemsProvider.listItems;
  createItem = itemsProvider.createItem;
  deleteItem = itemsProvider.deleteItem;
  updateItem = itemsProvider.updateItem;
  archiveItem = itemsProvider.archiveItem;
  unarchiveItem = itemsProvider.unarchiveItem;
  persistQuickscanDraft = itemsProvider.persistQuickscanDraft;
  quickscanSingle = itemsProvider.quickscanSingle;
  searchItems = itemsProvider.searchItems;

  // ─── Watchlist ──────────────────────────────────────────────────────────────
  listWatchlist = watchlistProvider.listWatchlist;
  addWatchlistItem = watchlistProvider.addWatchlistItem;
  updateWatchlistItem = watchlistProvider.updateWatchlistItem;
  removeWatchlistItem = watchlistProvider.removeWatchlistItem;
  removeWatchlistItems = watchlistProvider.removeWatchlistItems;
  convertWatchlistToItem = watchlistProvider.convertWatchlistToItem;

  // ─── Categories ─────────────────────────────────────────────────────────────
  getCategoryStore = categoryProvider.getCategoryStore;
  listCategorySummaries = categoryProvider.listCategorySummaries;
  listCategoryMissing = categoryProvider.listCategoryMissing;
  markCategoryItemOwned = categoryProvider.markCategoryItemOwned;
  followCategory = categoryProvider.followCategory;
  unfollowCategory = categoryProvider.unfollowCategory;
  listFollowedCategories = categoryProvider.listFollowedCategories;
  isFollowingCategory = categoryProvider.isFollowingCategory;
  getCategoryDeepDive = categoryProvider.getCategoryDeepDive;

  // ─── Alerts ─────────────────────────────────────────────────────────────────
  async listAlertsFeed(pagination?: PaginationParams): Promise<AlertFeedItem[]> {
    // The view `v_alerts_feed_v1` was never deployed — every call to this
    // returned [] silently because the .from() failed and the catch
    // returned []. The active server source of truth is GET
    // /alerts/trigger-history (alerts_feature_router.py:269), which reads
    // alert_trigger_history with the right RLS scoping. Found by
    // audit_full_chain.py 2026-05-01.
    const { API_LIMITS } = await import('@/constants/apiLimits');
    const { collectorsApi } = await import('../api/collectorsApi');
    const logger = (await import('../utils/logger')).default;

    const limit = pagination?.limit ?? API_LIMITS.ALERTS_DEFAULT;
    const offset = pagination?.offset ?? 0;
    try {
      const data = await collectorsApi.getAlertTriggerHistory();
      const triggers = (data?.triggers ?? []).slice(offset, offset + limit);
      return triggers.map((t) => ({
        id: t.id,
        // Server returns trigger_type (e.g. 'price_drop', 'milestone'); the
        // FE display used `type` or `alert_type` interchangeably.
        type: t.trigger_type ?? 'unknown',
        title: t.message ?? '',
        body: null,
        createdAt: t.created_at ?? new Date().toISOString(),
        itemId: t.item_id ?? null,
        watchlistItemId: null,
      }));
    } catch (err) {
      logger.error('[SupabaseDataProvider] listAlertsFeed error:', err);
      return [];
    }
  }

  /**
   * The user's standing alert rules — GET /alerts/mine
   * (alerts_feature_router.py:72), the same rows POST /alerts/mine writes.
   *
   * `collectorsApi.getMyAlerts` existed and was exported but had zero callers:
   * the Rules tab was reading the trigger *feed* instead. Paginated
   * client-side because the wrapper takes no params.
   */
  async listAlertRules(pagination?: PaginationParams): Promise<AlertRule[]> {
    const { API_LIMITS } = await import('@/constants/apiLimits');
    const { collectorsApi } = await import('../api/collectorsApi');
    const logger = (await import('../utils/logger')).default;

    const limit = pagination?.limit ?? API_LIMITS.ALERTS_DEFAULT;
    const offset = pagination?.offset ?? 0;
    try {
      const data = await collectorsApi.getMyAlerts();
      const rules = (data?.alerts ?? []).slice(offset, offset + limit);
      return rules.map((a) => ({
        id: a.id,
        itemId: a.item_id ?? null,
        category: a.category ?? null,
        triggerType: a.trigger_type ?? 'below_threshold',
        thresholdValue: typeof a.threshold_value === 'number' ? a.threshold_value : null,
        direction: a.direction === 'up' || a.direction === 'down' ? a.direction : null,
        active: a.active ?? true,
        createdAt: a.created_at ?? new Date().toISOString(),
      }));
    } catch (err) {
      logger.error('[SupabaseDataProvider] listAlertRules error:', err);
      return [];
    }
  }

  // ─── Chat / DM ──────────────────────────────────────────────────────────────
  listInboxThreads = chatProvider.listInboxThreads;
  listIncomingRequests = chatProvider.listIncomingRequests;
  requestDm = chatProvider.requestDm;
  decideDmRequest = chatProvider.decideDmRequest;
  markThreadRead = chatProvider.markThreadRead;
  getThreadMessages = chatProvider.getThreadMessages;
  sendMessage = chatProvider.sendMessage;
  setTyping = chatProvider.setTyping;
  clearTyping = chatProvider.clearTyping;
  isOtherUserTyping = chatProvider.isOtherUserTyping;
  getDmStatus = chatProvider.getDmStatus;
  getInboxUnreadCount = chatProvider.getInboxUnreadCount;

  // ─── Users ──────────────────────────────────────────────────────────────────
  getPublicUserProfile = userProvider.getPublicUserProfile;
  getMyProfile = userProvider.getMyProfile;
  searchUsers = userProvider.searchUsers;
  blockUser = userProvider.blockUser;
  unblockUser = userProvider.unblockUser;
  listBlockedUsers = userProvider.listBlockedUsers;
  isBlocked = userProvider.isBlocked;

  // ─── Analytics ──────────────────────────────────────────────────────────────
  getAnalyticsMetrics = buildPaintProvider.getAnalyticsMetrics;

  // ─── Build & Paint ──────────────────────────────────────────────────────────
  listBuildPaintProjects = buildPaintProvider.listBuildPaintProjects;
  createBuildPaintProject = buildPaintProvider.createBuildPaintProject;
  setBuildPaintProgress = buildPaintProvider.setBuildPaintProgress;
  markBuildPaintProjectComplete = buildPaintProvider.markBuildPaintProjectComplete;
  listBuildPaintSteps = buildPaintProvider.listBuildPaintSteps;
  addBuildPaintStep = buildPaintProvider.addBuildPaintStep;
  toggleBuildPaintStep = buildPaintProvider.toggleBuildPaintStep;
  listBuildPaintNotes = buildPaintProvider.listBuildPaintNotes;
  addBuildPaintNote = buildPaintProvider.addBuildPaintNote;
  listBuildPaintProjectsByCategory = buildPaintProvider.listBuildPaintProjectsByCategory;
  listBuildPaintProjectsByItem = buildPaintProvider.listBuildPaintProjectsByItem;
  applyStepTemplate = buildPaintProvider.applyStepTemplate;
  updateBuildPaintProject = buildPaintProvider.updateBuildPaintProject;

  // ─── Feedback ───────────────────────────────────────────────────────────────
  submitFeedback = feedbackProvider.submitFeedback;
  submitCorrection = feedbackProvider.submitCorrection;

  // ─── Market / Barcode ───────────────────────────────────────────────────────
  lookupByBarcode = marketProvider.lookupByBarcode;
  marketSearch = marketProvider.marketSearch;

  // ─── Presence ───────────────────────────────────────────────────────────────
  sendHeartbeat = presenceProvider.sendHeartbeat;
  goOffline = presenceProvider.goOffline;
  getUserPresence = presenceProvider.getUserPresence;
  getBatchPresence = presenceProvider.getBatchPresence;

  // ─── Activity Feed ──────────────────────────────────────────────────────────
  getUserActivity = activityProvider.getUserActivity;
  logActivity = activityProvider.logActivity;
  unifiedSearch = activityProvider.unifiedSearch;

  // ─── Events ─────────────────────────────────────────────────────────────────
  getEventById = eventsProvider.getEventById;
  listEvents = eventsProvider.listEvents;
  createEvent = eventsProvider.createEvent;
  rsvpEvent = eventsProvider.rsvpEvent;
  unrsvpEvent = eventsProvider.unrsvpEvent;
  updateEvent = eventsProvider.updateEvent;
  cancelEvent = eventsProvider.cancelEvent;
  duplicateEvent = eventsProvider.duplicateEvent;
  listEventTemplates = eventsProvider.listEventTemplates;
  createEventTemplate = eventsProvider.createEventTemplate;
  deleteEventTemplate = eventsProvider.deleteEventTemplate;
  searchEvents = eventsProvider.searchEvents;

  // shareEventViaDm stays here because it cross-references chat + event methods
  async shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
    const event = await this.getEventById(eventId);
    if (!event) {
      throw new Error(`Event not found: ${eventId}`);
    }

    const dmStatus = await this.getDmStatus(recipientUserId);
    let threadId: string;

    if (dmStatus === 'accepted') {
      const { supabase } = await import('../lib/supabase');
      // v_chat_inbox_v1 only surfaces accepted threads — no status column,
      // and the thread id lives in `thread_id` not `id`.
      const { data } = await supabase
        .from('v_chat_inbox_v1')
        .select('thread_id')
        .eq('other_user_id', recipientUserId)
        .maybeSingle();
      threadId = (data as Record<string, unknown> | null)?.thread_id as string;
      if (!threadId) {
        throw new Error('Could not find existing DM thread');
      }
    } else if (dmStatus === 'none') {
      threadId = await this.requestDm(recipientUserId);
    } else {
      throw new Error(`Cannot share event: DM status with user is "${dmStatus}"`);
    }

    const message =
      `\u{1F3AB} Check out this event: ${event.title}\n` +
      `\u{1F4C5} ${event.date}${event.time ? ' ' + event.time : ''}\n` +
      `\u{1F449} sparrow://events/${eventId}`;

    await this.sendMessage(threadId, message);
  }

  // ─── Sponsor Companies ──────────────────────────────────────────────────────
  registerSponsorCompany = eventsProvider.registerSponsorCompany;
  getMySponsorCompanies = eventsProvider.getMySponsorCompanies;
  updateSponsorCompany = eventsProvider.updateSponsorCompany;
  createSponsorEventCheckout = eventsProvider.createSponsorEventCheckout;
  createTicketCheckout = eventsProvider.createTicketCheckout;
  createSponsorSubscriptionCheckout = eventsProvider.createSponsorSubscriptionCheckout;

  // ─── Event Announcements ────────────────────────────────────────────────────
  listEventAnnouncements = eventsProvider.listEventAnnouncements;
  postEventAnnouncement = eventsProvider.postEventAnnouncement;
  markAnnouncementRead = eventsProvider.markAnnouncementRead;
  getUnreadAnnouncementCount = eventsProvider.getUnreadAnnouncementCount;

  // ─── Deal Desk (P2P Offers) ─────────────────────────────────────────────────
  proposeOffer = dealsProvider.proposeOffer;
  counterOffer = dealsProvider.counterOffer;
  respondToOffer = dealsProvider.respondToOffer;
  cancelOffer = dealsProvider.cancelOffer;
  listActiveOffers = dealsProvider.listActiveOffers;
  listDealHistory = dealsProvider.listDealHistory;
  getOfferDetail = dealsProvider.getOfferDetail;
  getUserReputation = dealsProvider.getUserReputation;
  toggleForSale = dealsProvider.toggleForSale;
  markShipped = dealsProvider.markShipped;
  completeDeal = dealsProvider.completeDeal;

  // ─── Multi-Marketplace Selling ──────────────────────────────────────────────
  listMarketplaceListings = dealsProvider.listMarketplaceListings;
  createMarketplaceListing = dealsProvider.createMarketplaceListing;
  updateMarketplaceListing = dealsProvider.updateMarketplaceListing;
  deleteMarketplaceListing = dealsProvider.deleteMarketplaceListing;
  listMarketplaceAccounts = dealsProvider.listMarketplaceAccounts;
  listMarketplaceSales = dealsProvider.listMarketplaceSales;
  getMarketplaceFeeSchedules = dealsProvider.getMarketplaceFeeSchedules;
}

// Singleton instance
export const supabaseDataProvider = new SupabaseDataProvider();
