/**
 * Barrel module — re-exports all domain API modules and assembles the
 * `collectorsApi` object so that every existing `import { collectorsApi }` or
 * `import { deleteAccount, ... }` continues to work without changes.
 */

// ── Re-export shared HTTP primitives & error class ─────────────────────────
import { get, post, del, patch, type ReqOpts } from "./httpClient";

// ── Import everything from domain modules to build the collectorsApi object ─
import * as intakeApi from "./intakeApi";
import * as itemsApi from "./itemsApi";
import * as marketplaceApi from "./marketplaceApi";
import * as dealsApi from "./dealsApi";
import * as gamificationApi from "./gamificationApi";
import * as eventsApi from "./eventsApi";
import * as chatApi from "./chatApi";
import * as portfolioApi from "./portfolioApi";
import * as socialApi from "./socialApi";
import * as alertsApi from "./alertsApi";
import * as notificationsApi from "./notificationsApi";
import * as predictApi from "./predictApi";
import * as settingsApi from "./settingsApi";
import * as dataMoatApi from "./dataMoatApi";
import * as collectionsApiModule from "./collectionsApi";
import * as setsApi from "./setsApi";
import * as sponsorApi from "./sponsorApi";
import * as gradingApi from "./gradingApi";
import * as miscApi from "./miscApi";
export { ApiError } from "./httpClient";

// ── Re-export shared types ─────────────────────────────────────────────────
export type { ServerUploadResponse, IntakeResultResponse, BillingStatus, NotificationItem, NotificationHistoryResponse } from "./types";

// ── Re-export standalone functions (used via named imports) ────────────────
export {
  deleteAccount,
  getBillingStatus,
  createCheckoutSession,
  createPortalSession,
  getUserActivity,
  logActivity,
  unifiedSearch,
  searchEvents,
  submitScanFeedback,
  multiDetect,
  getValueSummary,
} from "./miscApi";
export type { ValueSummaryData } from "./miscApi";

export {
  getNotificationHistory,
  markNotificationRead,
  markAllNotificationsRead,
} from "./notificationsApi";

// ── Assemble the unified collectorsApi object ──────────────────────────────
// Every method that was on the original object is mapped here, preserving
// the exact same keys and signatures.

export const collectorsApi = {
  // Watchlist
  fetchWatchlist: miscApi.fetchWatchlist,
  addToWatchlist: miscApi.addToWatchlist,

  // QuickScan
  quickscanSingle: intakeApi.quickscanSingle,

  // Intake
  intakeImageOnly: intakeApi.intakeImageOnly,
  quickscanBatch: intakeApi.quickscanBatch,

  // Insights
  fetchInsights: miscApi.fetchInsights,
  fetchHomeWidget: miscApi.fetchHomeWidget,

  // Screenshot intelligence
  analyzeScreenshot: intakeApi.analyzeScreenshot,

  // Feedback
  submitFeedback: miscApi.submitFeedback,
  submitCorrection: miscApi.submitCorrection,

  // Barcode / Market Data
  lookupByBarcode: miscApi.lookupByBarcode,

  marketSearch: marketplaceApi.marketSearch,

  // Price prediction
  getItemPriceTrend: predictApi.getItemPriceTrend,
  getPriceEvidence: predictApi.getPriceEvidence,

  // Photo upload
  uploadPhoto: itemsApi.uploadPhoto,
  getPresignedUploadUrl: itemsApi.getPresignedUploadUrl,
  deletePhoto: itemsApi.deletePhoto,
  listItemPhotos: itemsApi.listItemPhotos,

  // Provenance
  getProvenance: itemsApi.getProvenance,

  // Alert trigger history
  getAlertTriggerHistory: alertsApi.getAlertTriggerHistory,
  markTriggerRead: alertsApi.markTriggerRead,

  // Dossier
  getDossier: itemsApi.getDossier,
  getDossierSummary: itemsApi.getDossierSummary,
  getDossierExportUrl: itemsApi.getDossierExportUrl,

  // FX rates
  getFxRates: miscApi.getFxRates,

  // Marketplace aggregation
  marketplaceSearch: marketplaceApi.marketplaceSearch,
  marketplaceComps: marketplaceApi.marketplaceComps,

  // Taxonomy
  getTaxonomy: settingsApi.getTaxonomy,
  getTaxonomyCategories: settingsApi.getTaxonomyCategories,

  // URL Import
  processIntakeUrl: intakeApi.processIntakeUrl,
  processIntake: intakeApi.processIntake,
  intakeSave: intakeApi.intakeSave,

  // Price alerts
  getMyAlerts: alertsApi.getMyAlerts,
  createAlert: alertsApi.createAlert,
  deleteAlert: alertsApi.deleteAlert,

  // Push notifications
  registerPushToken: notificationsApi.registerPushToken,
  getNotificationPreferences: notificationsApi.getNotificationPreferences,
  updateNotificationPreferences: notificationsApi.updateNotificationPreferences,
  unregisterPushToken: notificationsApi.unregisterPushToken,

  processIntakeWithImage: intakeApi.processIntakeWithImage,

  // Smart Deal Agent — Mandates
  createMandate: dealsApi.createMandate,
  listMandates: dealsApi.listMandates,
  getMandate: dealsApi.getMandate,
  updateMandate: dealsApi.updateMandate,
  deleteMandate: dealsApi.deleteMandate,

  // Deals
  listDeals: dealsApi.listDeals,
  getDeal: dealsApi.getDeal,
  clickDeal: dealsApi.clickDeal,
  confirmDeal: dealsApi.confirmDeal,
  declineDeal: dealsApi.declineDeal,
  getDealStats: dealsApi.getDealStats,

  // Catalog Learning
  submitCatalogSuggestion: intakeApi.submitCatalogSuggestion,

  // Geolocation
  detectRegion: miscApi.detectRegion,

  // Affiliate links
  getAffiliateLinks: marketplaceApi.getAffiliateLinks,
  tagAffiliateUrl: marketplaceApi.tagAffiliateUrl,

  // Deal Desk (P2P Offers)
  proposeOffer: dealsApi.proposeOffer,
  counterOffer: dealsApi.counterOffer,
  respondToOffer: dealsApi.respondToOffer,
  cancelOffer: dealsApi.cancelOffer,
  markShipped: dealsApi.markShipped,
  completeDeal: dealsApi.completeDeal,
  listActiveOffers: dealsApi.listActiveOffers,
  listDealHistory: dealsApi.listDealHistory,
  getOfferDetail: dealsApi.getOfferDetail,
  getOfferEvidence: dealsApi.getOfferEvidence,
  getUserReputation: dealsApi.getUserReputation,
  toggleItemForSale: itemsApi.toggleItemForSale,

  // Item Images (multi-photo per item)
  listItemImages: itemsApi.listItemImages,
  uploadItemImage: itemsApi.uploadItemImage,
  deleteItemImage: itemsApi.deleteItemImage,
  reorderItemImages: itemsApi.reorderItemImages,

  // Drop Alerts
  subscribeDropAlert: eventsApi.subscribeDropAlert,
  unsubscribeDropAlert: eventsApi.unsubscribeDropAlert,
  listMyDropAlerts: eventsApi.listMyDropAlerts,

  // Onboarding / User Settings
  saveFollowedCategories: settingsApi.saveFollowedCategories,
  getFollowedCategories: settingsApi.getFollowedCategories,
  getAlertPreferences: settingsApi.getAlertPreferences,
  updateAlertPreferences: settingsApi.updateAlertPreferences,

  // Catalog Browser
  browseCatalogItems: intakeApi.browseCatalogItems,
  getCatalogItemPrice: intakeApi.getCatalogItemPrice,
  getCatalogCollections: intakeApi.getCatalogCollections,

  // Progress Tracking
  getItemProgress: itemsApi.getItemProgress,
  updateItemProgress: itemsApi.updateItemProgress,

  // Item Attributes / Size
  updateItemAttributes: itemsApi.updateItemAttributes,

  // Grading Service Integration
  gradingLookup: gradingApi.gradingLookup,
  gradingPopulation: gradingApi.gradingPopulation,
  gradingServices: gradingApi.gradingServices,

  // Gamification
  getGamificationProfile: gamificationApi.getGamificationProfile,
  getPublicGamificationProfile: gamificationApi.getPublicGamificationProfile,
  getAchievements: gamificationApi.getAchievements,
  getRecentAchievements: gamificationApi.getRecentAchievements,
  getActiveChallenges: gamificationApi.getActiveChallenges,
  getLeaderboard: gamificationApi.getLeaderboard,

  // Marketplace Listings (Multi-Marketplace Selling)
  createMarketplaceListing: marketplaceApi.createMarketplaceListing,
  listMarketplaceListings: marketplaceApi.listMarketplaceListings,
  updateMarketplaceListing: marketplaceApi.updateMarketplaceListing,
  deleteMarketplaceListing: marketplaceApi.deleteMarketplaceListing,
  publishMarketplaceListing: marketplaceApi.publishMarketplaceListing,
  calculateMarketplaceFees: marketplaceApi.calculateMarketplaceFees,

  // Portfolio Analytics
  getPortfolioOverview: portfolioApi.getPortfolioOverview,
  getPortfolioTimeseries: portfolioApi.getPortfolioTimeseries,
  getPortfolioCategoryBreakdown: portfolioApi.getPortfolioCategoryBreakdown,
  getPortfolioCategoryStats: portfolioApi.getPortfolioCategoryStats,
  getCategoryHealth: portfolioApi.getCategoryHealth,
  getCategoryCrossCorrelation: portfolioApi.getCategoryCrossCorrelation,

  // Collections
  listCollections: collectionsApiModule.listCollections,
  getCollectionDetail: collectionsApiModule.getCollectionDetail,
  getCollectionProgress: collectionsApiModule.getCollectionProgress,
  getUserCollectionProgress: collectionsApiModule.getUserCollectionProgress,

  // Insights (aliased)
  getPersonalizedInsights: miscApi.getPersonalizedInsights,
  getHomeWidget: miscApi.getHomeWidget,

  // Items Export
  exportItemsOverview: miscApi.exportItemsOverview,
  exportItemsFull: miscApi.exportItemsFull,

  // Insurance Valuation Export
  getInsuranceReportUrl: miscApi.getInsuranceReportUrl,

  // Social
  searchUsers: socialApi.searchUsers,
  blockUser: socialApi.blockUser,
  unblockUser: socialApi.unblockUser,
  listBlockedUsers: socialApi.listBlockedUsers,

  // Chat / DM
  getChatThreads: chatApi.getChatThreads,
  getChatMessages: chatApi.getChatMessages,
  sendChatMessage: chatApi.sendChatMessage,
  markChatThreadRead: chatApi.markChatThreadRead,
  deleteChatMessage: chatApi.deleteChatMessage,
  editChatMessage: chatApi.editChatMessage,
  getChatUnreadCount: chatApi.getChatUnreadCount,

  // Data Moat Analytics
  getSupplyTrends: dataMoatApi.getSupplyTrends,
  getDemandHeat: dataMoatApi.getDemandHeat,
  getScarcityScores: dataMoatApi.getScarcityScores,
  getTopMovers: dataMoatApi.getTopMovers,

  // Trends & Deep-Dive
  getCollectionTrends: miscApi.getCollectionTrends,
  getCategoryDeepDive: miscApi.getCategoryDeepDive,
  getItemTrends: miscApi.getItemTrends,

  // Events — Core CRUD
  createEvent: eventsApi.createEvent,
  getEventById: eventsApi.getEventById,
  updateEvent: eventsApi.updateEvent,
  deleteEvent: eventsApi.deleteEvent,
  duplicateEvent: eventsApi.duplicateEvent,

  // Events — RSVP
  rsvpEvent: eventsApi.rsvpEvent,
  unrsvpEvent: eventsApi.unrsvpEvent,

  // Events — Ticketing
  createTicketCheckout: eventsApi.createTicketCheckout,

  // Events — Announcements
  listEventAnnouncements: eventsApi.listEventAnnouncements,
  postEventAnnouncement: eventsApi.postEventAnnouncement,
  markAnnouncementRead: eventsApi.markAnnouncementRead,
  batchMarkAnnouncementsRead: eventsApi.batchMarkAnnouncementsRead,
  getUnreadAnnouncementCount: eventsApi.getUnreadAnnouncementCount,

  // Events — Templates
  listEventTemplates: eventsApi.listEventTemplates,
  createEventTemplate: eventsApi.createEventTemplate,
  deleteEventTemplate: eventsApi.deleteEventTemplate,

  // Events — Drop Alerts & Categories
  getNearbyEvents: eventsApi.getNearbyEvents,
  getFollowedEventCategories: eventsApi.getFollowedEventCategories,
  followEventCategory: eventsApi.followEventCategory,
  unfollowEventCategory: eventsApi.unfollowEventCategory,

  // Set / Collection Tracking
  listSets: setsApi.listSets,
  getSetDetail: setsApi.getSetDetail,
  getSetProgress: setsApi.getSetProgress,
  updateSetProgress: setsApi.updateSetProgress,
  getMySetProgress: setsApi.getMySetProgress,

  // Sponsor Companies
  listMySponsorCompanies: sponsorApi.listMySponsorCompanies,
  createSponsorCompany: sponsorApi.createSponsorCompany,
  getSponsorCompany: sponsorApi.getSponsorCompany,
  updateSponsorCompany: sponsorApi.updateSponsorCompany,
  deleteSponsorCompany: sponsorApi.deleteSponsorCompany,
  createSponsorEventCheckout: sponsorApi.createSponsorEventCheckout,
  createSponsorSubscriptionCheckout: sponsorApi.createSponsorSubscriptionCheckout,

  // Build & Paint Step Templates
  getStepTemplates: miscApi.getStepTemplates,

  // Task Queue
  enqueueTask: miscApi.enqueueTask,
  getTaskStatus: miscApi.getTaskStatus,

  // Marketplace Listing Accounts
  listMarketplaceAccounts: marketplaceApi.listMarketplaceAccounts,
  connectMarketplaceAccount: marketplaceApi.connectMarketplaceAccount,
  disconnectMarketplaceAccount: marketplaceApi.disconnectMarketplaceAccount,
  getMarketplaceFeeSchedules: marketplaceApi.getMarketplaceFeeSchedules,
  listMarketplaceSales: marketplaceApi.listMarketplaceSales,
  recordMarketplaceSale: marketplaceApi.recordMarketplaceSale,

  // Deal Risk Flags
  getDealRiskFlags: dealsApi.getDealRiskFlags,

  // Mandate Forecast
  getMandateForecast: dealsApi.getMandateForecast,

  // Verified Sales (Ground Truth)
  submitVerifiedSale: miscApi.submitVerifiedSale,
  listVerifiedSales: miscApi.listVerifiedSales,

  // Sponsor Analytics
  getSponsorAnalytics: sponsorApi.getSponsorAnalytics,

  // Supply & Demand Indicators
  getDemandHeatByRegion: dataMoatApi.getDemandHeatByRegion,
  getPredictionAccuracy: dataMoatApi.getPredictionAccuracy,

  // Generic HTTP helpers (used by DataProvider implementations)
  get: <T = unknown>(path: string, opts?: ReqOpts) => get<T>(path, opts),
  post: <T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts) => post<T>(path, body, opts),
  patch: <T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts) => patch<T>(path, body, opts),
  delete: <T = unknown>(path: string, opts?: ReqOpts) => del<T>(path, opts),
};
