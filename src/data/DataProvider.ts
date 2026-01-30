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
  QuickScanResult,
  PublicUserProfile,
  CategoryStoreData,
  DmThread,
  DmRequest,
  DmMessage,
  AnalyticsMetrics,
} from './types';

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
   * Create a new item in the collection.
   * @param input - Item data to create
   * @returns The created item
   */
  createItem(input: CreateItemInput): Promise<Item>;

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
   * @param userId - The user's ID
   */
  getPublicUserProfile(userId: string): Promise<PublicUserProfile | null>;

  /**
   * Get category store data for Amazon Brand Store style layout.
   * Returns category info, spotlight slides, items, events, and friends.
   * @param categoryId - The category ID
   */
  getCategoryStore(categoryId: string): Promise<CategoryStoreData | null>;

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
}
