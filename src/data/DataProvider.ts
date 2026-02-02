/**
 * DataProvider interface.
 * All data access from UI should go through this interface.
 * Implementations: MockDataProvider, SupabaseDataProvider
 */

import type {
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
  MarketHit,
  MarketSearchOptions,
  MarketSearchResult,
} from './types';
import type { CollectorsEvent } from './events';

export interface DataProvider {
  /**
   * Get portfolio summary (total value, delta percentage, item count).
   */
  getPortfolioSummary(): Promise<PortfolioSummary>;

  /**
   * List all items in the user's collection.
   */
  listItems(): Promise<Item[]>;

  /**
   * List watchlist items for a user.
   * @param userId - The user's ID (required for Supabase, ignored in mock)
   */
  listWatchlist(userId: string): Promise<WatchlistItem[]>;

  /**
   * Add an item to the watchlist.
   * Mock: appends to in-memory list.
   * Real: calls rpc_add_watchlist_item_v1.
   * @param input - Watchlist item data
   * @returns The created watchlist item
   */
  addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem>;

  /**
   * Remove an item from the watchlist.
   * Real: calls rpc_remove_watchlist_item_v1.
   * @param id - Watchlist item ID
   */
  removeWatchlistItem(id: string): Promise<void>;

  /**
   * Create a new item in the collection.
   * @param input - Item data to create
   * @returns The created item
   */
  createItem(input: CreateItemInput): Promise<Item>;

  /**
   * Persist a QuickScan draft as a new item.
   * Mock: appends to in-memory items store.
   * Real: calls rpc_create_item_v1.
   * @param input - QuickScan draft data
   * @returns The persisted item
   */
  persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem>;

  /**
   * Run QuickScan on a single image.
   * Returns attributes + prediction (no save).
   */
  quickscanSingle(): Promise<QuickScanResult>;

  /**
   * Search items by query string.
   * Returns empty array if query is empty.
   * @param query - Search term to match against item name/title
   */
  searchItems(query: string): Promise<Item[]>;

  /**
   * Get public user profile by ID.
   * Queries user_public_profile_v1 view (RLS: public SELECT).
   * Returns null if user not found.
   * Uses in-memory cache to prevent repeated lookups.
   * @param userId - The user's ID
   */
  getPublicUserProfile(userId: string): Promise<PublicUserProfile | null>;

  /**
   * Get current authenticated user's profile.
   * Returns null if not authenticated or profile not found.
   * Uses auth.uid() server-side.
   */
  getMyProfile(): Promise<PublicUserProfile | null>;

  /**
   * Get category store data for Amazon Brand Store style layout.
   * Returns category info, spotlight slides, items, events, and friends.
   * @param categoryId - The category ID
   */
  getCategoryStore(categoryId: string): Promise<CategoryStoreData | null>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Browsing (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * List all categories with completion stats.
   * Mock: derived from static CATEGORIES.
   * Real: reads from v_category_summaries_v1.
   */
  listCategorySummaries(): Promise<CategorySummary[]>;

  /**
   * List missing items for a category (items user doesn't own).
   * Mock: returns generated demo data.
   * Real: reads from v_category_missing_items_v1.
   * @param categoryId - The category ID
   */
  listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Alerts Feed (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * List recent alert events for the current user.
   * Mock: returns demo alerts.
   * Real: reads from v_alerts_feed_v1.
   */
  listAlertsFeed(): Promise<AlertFeedItem[]>;

  // ─────────────────────────────────────────────────────────────────────────────
  // DM / Inbox methods
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * List all DM threads for the current user (inbox).
   * Reads from v_chat_inbox_v1.
   */
  listInboxThreads(): Promise<DmThread[]>;

  /**
   * List incoming DM requests (pending threads where current user is recipient).
   */
  listIncomingRequests(): Promise<DmRequest[]>;

  /**
   * Request a DM with another user.
   * Calls rpc_request_dm_v1.
   * @param toUserId - Target user ID
   * @param message - Optional initial message
   * @returns The created thread ID
   */
  requestDm(toUserId: string, message?: string): Promise<string>;

  /**
   * Accept or decline a DM request.
   * Calls rpc_decide_dm_request_v1.
   * @param threadId - Thread ID
   * @param accept - true to accept, false to decline
   */
  decideDmRequest(threadId: string, accept: boolean): Promise<void>;

  /**
   * Mark a thread as read.
   * Calls rpc_mark_thread_read_v1.
   * @param threadId - Thread ID
   */
  markThreadRead(threadId: string): Promise<void>;

  /**
   * Get messages for a thread.
   * @param threadId - Thread ID
   */
  getThreadMessages(threadId: string): Promise<DmMessage[]>;

  /**
   * Send a message in a thread.
   * Mock mode: appends to in-memory store.
   * Real mode: calls rpc_send_message_v1.
   * @param threadId - Thread ID
   * @param body - Message text
   */
  sendMessage(threadId: string, body: string): Promise<DmMessage>;

  /**
   * Get DM connection status with another user.
   * Returns: 'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'
   */
  getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'>;

  /**
   * Get total unread count for inbox (threads + requests).
   * Used for badge display.
   */
  getInboxUnreadCount(): Promise<number>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Analytics
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Get analytics metrics for the Analytics screen.
   * Includes build/paint project stats and Twitch creator stats.
   */
  getAnalyticsMetrics(): Promise<AnalyticsMetrics>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Build & Paint Projects
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * List all build & paint projects for the current user.
   * Mock: returns in-memory projects.
   * Real: reads from v_build_paint_projects_v1.
   */
  listBuildPaintProjects(): Promise<BuildPaintProject[]>;

  /**
   * Create a new build & paint project.
   * Mock: appends to in-memory store.
   * Real: calls rpc_create_build_paint_project_v1.
   */
  createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject>;

  /**
   * Set progress (percent + optional status) on a project.
   * Mock: updates in-memory.
   * Real: calls rpc_set_build_paint_progress_v1.
   */
  setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void>;

  /**
   * Mark a project as complete or incomplete.
   * Mock: updates in-memory.
   * Real: calls rpc_mark_build_paint_project_complete_v1.
   */
  markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void>;

  /**
   * List steps for a project.
   * Mock: returns in-memory steps.
   * Real: reads from v_build_paint_project_steps_v1 filtered by projectId.
   */
  listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]>;

  /**
   * Add a step to a project.
   * Mock: appends to in-memory.
   * Real: calls rpc_add_build_paint_step_v1.
   */
  addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep>;

  /**
   * Toggle a step's done status.
   * Mock: updates in-memory.
   * Real: calls rpc_toggle_build_paint_step_v1.
   */
  toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void>;

  /**
   * List notes for a project.
   * Mock: returns in-memory notes.
   * Real: reads from v_build_paint_project_notes_v1 filtered by projectId.
   */
  listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]>;

  /**
   * Add a note to a project.
   * Mock: appends to in-memory.
   * Real: calls rpc_add_build_paint_note_v1.
   */
  addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Feedback
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Submit feedback on an item's price prediction.
   * @param itemId - The item's UUID
   * @param feedbackType - Type: 'sale_price' | 'disagree' | 'accurate'
   * @param value - Optional value (e.g., actual sale price)
   * @returns Promise with success status
   */
  submitFeedback(
    itemId: string,
    feedbackType: 'sale_price' | 'disagree' | 'accurate',
    value?: string,
  ): Promise<{ success: boolean; feedbackId?: string }>;

  /**
   * Submit corrections to training item data.
   * @param itemId - The training item's UUID
   * @param corrections - Object with corrected fields
   * @returns Promise with success status
   */
  submitCorrection(
    itemId: string,
    corrections: {
      correctedPrice?: number;
      correctedCondition?: string;
      correctedCategory?: string;
      notes?: string;
    },
  ): Promise<{ success: boolean }>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Ownership
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Mark a category item as owned.
   * @param categoryItemId - The category item's UUID
   * @param quantity - Number owned (default 1)
   * @param notes - Optional notes about ownership
   * @returns Promise with success status
   */
  markCategoryItemOwned(
    categoryItemId: string,
    quantity?: number,
    notes?: string,
  ): Promise<{ success: boolean }>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Watchlist → Portfolio Conversion
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Convert a watchlist item to a portfolio item ("I Got It!" flow).
   * Creates a new item in the collection and removes from watchlist.
   * @param watchlistItemId - The watchlist item's ID
   * @param actualPrice - The actual purchase price (for ML feedback)
   * @param notes - Optional notes about the acquisition
   * @returns The created portfolio item
   */
  convertWatchlistToItem(
    watchlistItemId: string,
    actualPrice?: number,
    notes?: string,
  ): Promise<Item>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Get event by ID.
   * Mock: returns from static EVENTS array.
   * Real: reads from events table.
   * @param eventId - The event ID
   */
  getEventById(eventId: string): Promise<CollectorsEvent | null>;

  /**
   * List all upcoming events.
   * Mock: returns from static EVENTS array.
   * Real: reads from events table filtered by date >= now.
   */
  listEvents(): Promise<CollectorsEvent[]>;

  // ─────────────────────────────────────────────────────────────────────────────
  // Barcode / Market Data
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Lookup product info by barcode (EAN-13, UPC-A, ISBN).
   * Returns prefill data for item creation including category, price band, etc.
   * Mock: returns fixtures for known barcodes.
   * Real: queries product databases and market sources.
   * @param barcode - The barcode value
   * @param opts - Optional: codeType hint (ean13, upc_a, isbn)
   */
  lookupByBarcode(
    barcode: string,
    opts?: { codeType?: string },
  ): Promise<BarcodeLookupResult>;

  /**
   * Search market data across multiple providers.
   * Aggregates and dedupes results from all configured adapters.
   * Mock: returns demo hits.
   * Real: queries eBay, TCGPlayer, etc. via adapters.
   * @param query - Search query
   * @param opts - Search options (category, limit, soldOnly, etc.)
   */
  marketSearch(
    query: string,
    opts?: MarketSearchOptions,
  ): Promise<MarketSearchResult>;
}
