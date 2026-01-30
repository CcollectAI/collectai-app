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
}
