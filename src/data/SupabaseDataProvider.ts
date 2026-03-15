/**
 * SupabaseDataProvider — fetches real data from Supabase.
 *
 * This class delegates to domain-specific provider modules in ./providers/.
 * It implements the DataProvider interface and is the single entry point
 * for all Supabase-backed data access.
 */

import type { DataProvider } from './DataProvider';
import type {
  CurrencyCode,
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
  DmThreadStatus,
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  PaintRecipe,
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
    // Kept inline — small single-method domain, not worth a separate file
    const { API_LIMITS } = await import('@/constants/apiLimits');
    const { supabase } = await import('../lib/supabase');
    const logger = (await import('../utils/logger')).default;

    const limit = pagination?.limit ?? API_LIMITS.ALERTS_DEFAULT;
    const offset = pagination?.offset ?? 0;
    const { data, error } = await supabase
      .from('v_alerts_feed_v1')
      .select('id, type, alert_type, title, body, category, item_id, item_ref, created_at, read, trigger_value')
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      logger.warn('[SupabaseDataProvider] listAlertsFeed error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      id: row.id as string,
      type: (row.type ?? row.alert_type ?? 'unknown') as string,
      title: (row.title as string | null) ?? '',
      body: (row.body as string | null) ?? null,
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
      itemId: (row.item_id as string | null) ?? null,
      watchlistItemId: (row.watchlist_item_id as string | null) ?? null,
    }));
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
      const { data } = await supabase
        .from('v_chat_inbox_v1')
        .select('id')
        .eq('other_user_id', recipientUserId)
        .eq('status', 'accepted')
        .maybeSingle();
      threadId = (data as Record<string, unknown> | null)?.id as string;
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
      `\u{1F449} collectai://events/${eventId}`;

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
