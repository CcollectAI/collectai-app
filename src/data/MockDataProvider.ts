/**
 * MockDataProvider — returns mock/demo data.
 *
 * This class delegates to domain-specific mock modules in ./mocks/.
 * It implements the DataProvider interface and is the single entry point
 * for all mock data access.
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
  Offer,
  OfferEvent,
  UserReputation,
} from './types';
import type { CollectorsEvent, CreateEventInput, EventTemplate, EventAnnouncement, SponsorCompany } from './events';
import { mockSponsorCompanies } from './mocks/mockState';

// Domain providers
import * as portfolioProvider from './mocks/mockPortfolioProvider';
import * as itemsProvider from './mocks/mockItemsProvider';
import * as watchlistProvider from './mocks/mockWatchlistProvider';
import * as categoryProvider from './mocks/mockCategoryProvider';
import * as chatProvider from './mocks/mockChatProvider';
import * as userProvider from './mocks/mockUserProvider';
import * as eventsProvider from './mocks/mockEventsProvider';
import * as buildPaintProvider from './mocks/mockBuildPaintProvider';
import * as feedbackProvider from './mocks/mockFeedbackProvider';
import * as alertProvider from './mocks/mockAlertProvider';
import * as marketProvider from './mocks/mockMarketProvider';
import * as presenceProvider from './mocks/mockPresenceProvider';
import * as activityProvider from './mocks/mockActivityProvider';
import * as dealsProvider from './mocks/mockDealsProvider';

export class MockDataProvider implements DataProvider {

  // ─── Portfolio ───────────────────────────────────────────────────────────────
  getPortfolioSummary = portfolioProvider.getPortfolioSummary;

  // ─── Items ──────────────────────────────────────────────────────────────────
  listItems = itemsProvider.listItems;
  listArchivedItems = itemsProvider.listArchivedItems;
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
  listAlertsFeed = alertProvider.listAlertsFeed;
  listAlertRules = alertProvider.listAlertRules;

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

  // createEvent needs to pass sponsor companies from shared state
  async createEvent(input: CreateEventInput): Promise<CollectorsEvent> {
    return eventsProvider.createEvent(input, mockSponsorCompanies);
  }

  rsvpEvent = eventsProvider.rsvpEvent;
  unrsvpEvent = eventsProvider.unrsvpEvent;
  shareEventViaDm = eventsProvider.shareEventViaDm;
  updateEvent = eventsProvider.updateEvent;
  cancelEvent = eventsProvider.cancelEvent;
  duplicateEvent = eventsProvider.duplicateEvent;
  listEventTemplates = eventsProvider.listEventTemplates;
  createEventTemplate = eventsProvider.createEventTemplate;
  deleteEventTemplate = eventsProvider.deleteEventTemplate;
  searchEvents = eventsProvider.searchEvents;

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
  toggleForSale = dealsProvider.toggleForSale;

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
export const mockDataProvider = new MockDataProvider();
