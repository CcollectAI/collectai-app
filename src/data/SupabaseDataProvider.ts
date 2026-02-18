/**
 * SupabaseDataProvider — fetches real data from Supabase.
 * Uses the existing supabase client from src/lib/supabase.ts.
 * Returns stable shapes (no raw Supabase responses to UI).
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
  DmThreadStatus,
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  CreateBuildPaintProjectInput,
  BarcodeLookupResult,
  MarketSearchOptions,
  MarketSearchResult,
} from './types';
import { getCategoryById } from './categories';
import logger from '../utils/logger';
import type { CollectorsEvent, CreateEventInput } from './events';
import { supabase } from '../lib/supabase';
import { collectorsApi } from '../api/collectorsApi';

export class SupabaseDataProvider implements DataProvider {
  // In-memory profile cache to prevent repeated lookups
  private profileCache: Map<string, PublicUserProfile | null> = new Map();
  private myProfileCache: PublicUserProfile | null | undefined = undefined;

  /**
   * Assert that an RPC is implemented. Throws explicit error in real mode
   * when attempting to use a mutation that has no backend RPC yet.
   */
  private assertRpcAvailable(rpcName: string, implemented: boolean): void {
    if (!implemented) {
      throw new Error(
        `RPC_NOT_IMPLEMENTED: ${rpcName} is required for this mutation but not yet available. ` +
        `Direct table writes are prohibited in real mode.`
      );
    }
  }

  /**
   * Assert that a view is available. Throws explicit error in real mode
   * when attempting to read from a view that doesn't exist yet.
   */
  private assertViewAvailable(viewName: string, implemented: boolean): void {
    if (!implemented) {
      throw new Error(
        `VIEW_NOT_AVAILABLE: ${viewName} is required for this read but not yet created. ` +
        `Create the view in Supabase or use mock mode.`
      );
    }
  }

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    // Fetch portfolio values series
    const { data: valuesData, error: valuesError } = await supabase
      .from('portfolio_values')
      .select('at,value')
      .order('at', { ascending: true })
      .limit(365);

    if (valuesError) {
      logger.warn('[SupabaseDataProvider] getPortfolioSummary error:', valuesError);
      return { total: 0, deltaPct: 0, itemCount: 0 };
    }

    const rows = (valuesData ?? []) as { at: string; value: number }[];

    let total = 0;
    let deltaPct = 0;

    if (rows.length > 0) {
      const first = Number(rows[0].value || 0);
      const last = Number(rows[rows.length - 1].value || 0);
      total = last;
      deltaPct = first ? ((last - first) / first) * 100 : 0;
    }

    // Get item count
    const { count, error: countError } = await supabase
      .from('items')
      .select('id', { count: 'exact', head: true });

    if (countError) {
      logger.warn('[SupabaseDataProvider] item count error:', countError);
    }

    return {
      total,
      deltaPct,
      itemCount: count ?? 0,
    };
  }

  async listItems(pagination?: PaginationParams): Promise<Item[]> {
    const limit = pagination?.limit ?? 200;
    const offset = pagination?.offset ?? 0;
    // JOIN price_predictions via FK (item_id → items.id)
    const { data, error } = await supabase
      .from('items')
      .select('id, title, category, updated_at, attributes_json, taxonomy_version, subtype_id, collections, price_predictions(q10, q50, q90, conf_score, asof)')
      .order('updated_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      logger.warn('[SupabaseDataProvider] listItems error:', error);
      return [];
    }

    type PredRow = { q10: number | null; q50: number | null; q90: number | null; conf_score: number | null; asof: string | null };
    type ItemRow = {
      id: string;
      title?: string | null;
      category?: string | null;
      updated_at?: string | null;
      attributes_json?: Record<string, unknown> | null;
      taxonomy_version?: string | null;
      subtype_id?: string | null;
      collections?: string[] | null;
      price_predictions?: PredRow[];
    };

    const rows = (data ?? []) as ItemRow[];

    return rows.map((r) => {
      // Pick latest prediction by asof
      const preds = (r.price_predictions ?? []).sort(
        (a, b) => (b.asof ?? '').localeCompare(a.asof ?? ''),
      );
      const latest = preds[0];

      return {
        id: r.id,
        name: r.title ?? 'Untitled',
        category: r.category || 'Uncategorized',
        subtypeId: r.subtype_id ?? undefined,
        taxonomyVersion: r.taxonomy_version ?? undefined,
        collections: r.collections ?? undefined,
        attributesJson: r.attributes_json ?? undefined,
        price: latest?.q50 ?? 0,
        priceBand: latest
          ? { q10: latest.q10 ?? 0, q50: latest.q50 ?? 0, q90: latest.q90 ?? 0, confidence: latest.conf_score ?? 0, currency: 'EUR' }
          : undefined,
        imageUrl: undefined,
        updatedAt: r.updated_at ?? undefined,
      };
    });
  }

  async listWatchlist(_userId: string): Promise<WatchlistItem[]> {
    // Reads via VIEW only (auth.uid() is used server-side)
    const { data, error } = await supabase
      .from('v_watchlist_items_v1')
      .select('id,title,priority,owned,target_price,currency,category,notes,created_at');

    if (error) {
      logger.warn('[SupabaseDataProvider] listWatchlist error:', error);
      return [];
    }

    const rows = (data ?? []) as {
      id: string;
      title: string;
      priority: 'high' | 'medium' | 'low';
      owned: boolean;
      target_price: number | null;
      currency: string;
      category?: string | null;
      notes?: string | null;
      created_at?: string | null;
    }[];

    return rows.map((r) => ({
      id: r.id,
      title: r.title,
      priority: r.priority || 'medium',
      owned: r.owned ?? false,
      targetPrice: r.target_price,
      currency: r.currency || 'EUR',
      category: r.category ?? undefined,
      notes: r.notes ?? undefined,
      createdAt: r.created_at ?? undefined,
    }));
  }

  async addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
    // Writes via RPC only (auth.uid() enforced server-side)
    const { data, error } = await supabase.rpc('rpc_add_watchlist_item_v1', {
      p_title: input.title,
      p_category: input.category,
      p_target_price: input.targetPrice ?? null,
      p_notes: input.notes ?? null,
      p_priority: input.priority || 'medium',
    });

    if (error) {
      logger.error('[SupabaseDataProvider] addWatchlistItem RPC error:', error);
      throw new Error(error.message || 'Failed to add watchlist item');
    }

    // RPC returns a row
    const r = (Array.isArray(data) ? data[0] : data) as Record<string, unknown>;
    if (!r) {
      throw new Error('No data returned from RPC');
    }

    return {
      id: r.id as string,
      title: r.title as string,
      priority: (r.priority as 'high' | 'medium' | 'low') || 'medium',
      owned: (r.owned as boolean) ?? false,
      targetPrice: (r.target_price as number | null) ?? null,
      currency: (r.currency as string) || 'EUR',
      category: r.category as string | undefined,
      notes: r.notes as string | undefined,
      createdAt: r.created_at as string | undefined,
    };
  }

  async removeWatchlistItem(id: string): Promise<void> {
    // Writes via RPC only (ownership enforced server-side)
    const { error } = await supabase.rpc('rpc_remove_watchlist_item_v1', {
      p_id: id,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] removeWatchlistItem RPC error:', error);
      throw new Error(error.message || 'Failed to remove watchlist item');
    }
  }

  async createItem(input: CreateItemInput): Promise<Item> {
    const { data, error } = await supabase.rpc('rpc_create_item_v1', {
      p_title: input.name,
      p_category: input.category,
      p_image_url: input.imageUrl ?? null,
      p_attributes: {},
      p_notes: null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] createItem RPC error:', error);
      throw new Error(error.message || 'Failed to create item');
    }

    const row = data as Record<string, unknown>;
    const images = row.images as string[] | null;

    return {
      id: row.id as string,
      name: (row.title as string | null) ?? input.name,
      category: (row.category as string | null) ?? input.category,
      price: 0, // No value column in items table
      imageUrl: images?.[0] ?? undefined,
      updatedAt: (row.updated_at as string | null) ?? undefined,
    };
  }

  async deleteItem(itemId: string): Promise<void> {
    const { error } = await supabase
      .from('items')
      .delete()
      .eq('id', itemId);

    if (error) {
      logger.error('[SupabaseDataProvider] deleteItem error:', error);
      throw new Error(error.message || 'Failed to delete item');
    }
  }

  async updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>>): Promise<Item> {
    const updatePayload: Record<string, unknown> = {};
    if (patch.name !== undefined) updatePayload.name = patch.name;
    if (patch.category !== undefined) updatePayload.category = patch.category;
    if (patch.price !== undefined) updatePayload.price = patch.price;
    if (patch.imageUrl !== undefined) updatePayload.image_url = patch.imageUrl;

    const { data, error } = await supabase
      .from('items')
      .update(updatePayload)
      .eq('id', itemId)
      .select('id, name, category, price, image_url, updated_at')
      .single();

    if (error || !data) {
      logger.error('[SupabaseDataProvider] updateItem error:', error);
      throw new Error(error?.message || 'Failed to update item');
    }

    return {
      id: data.id,
      name: data.name,
      category: data.category,
      price: data.price,
      imageUrl: data.image_url,
      updatedAt: data.updated_at,
    };
  }

  async archiveItem(itemId: string): Promise<void> {
    // Merge _archived: true into the existing attributes_json via JSONB concat
    const { error } = await supabase.rpc('rpc_archive_item_v1', {
      p_item_id: itemId,
    });

    if (error) {
      // Fallback: direct update if RPC not yet deployed
      const { error: updateError } = await supabase
        .from('items')
        .update({
          attributes_json: supabase.rpc('jsonb_set_archived', { p_item_id: itemId }) as unknown,
        } as Record<string, unknown>)
        .eq('id', itemId);

      // If RPC fallback also fails, try raw SQL-style update
      if (updateError) {
        const { error: rawError } = await supabase
          .from('items')
          .update({ archived_at: new Date().toISOString() } as Record<string, unknown>)
          .eq('id', itemId);

        if (rawError) {
          logger.error('[SupabaseDataProvider] archiveItem error:', rawError);
          throw new Error(rawError.message || 'Failed to archive item');
        }
      }
    }
  }

  async persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
    const { data, error } = await supabase.rpc('rpc_create_item_v1', {
      p_title: input.title ?? 'Untitled Scan',
      p_category: input.categoryId ?? 'uncategorized',
      p_image_url: input.photoUri ?? null,
      p_attributes: input.attributes ?? {},
      p_notes: input.notes ?? null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] persistQuickscanDraft RPC error:', error);
      throw new Error(error.message || 'Failed to persist QuickScan draft');
    }

    const row = data as Record<string, unknown>;
    const images = row.images as string[] | null;

    return {
      id: row.id as string,
      title: (row.title as string | null) ?? input.title ?? 'Untitled Scan',
      categoryId: (row.category as string | null) ?? input.categoryId ?? 'uncategorized',
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
      imageUrl: images?.[0] ?? null,
    };
  }

  async quickscanSingle(): Promise<QuickScanResult> {
    // Call HTTP endpoint via collectorsApi
    const res = await collectorsApi.quickscanSingle() as Record<string, unknown>;

    // Map snake_case response to camelCase
    const attrs = (res.attributes ?? {}) as Record<string, unknown>;
    const pred = (res.prediction ?? {}) as Record<string, unknown>;

    return {
      itemId: (res.item_id as string | null) ?? null,
      attributes: {
        category: (attrs.category as string | null) ?? '',
        editionGuess: (attrs.edition_guess as string | null) ?? null,
        conditionGuess: (attrs.condition_guess as string | null) ?? null,
        rarityScore: (attrs.rarity_score as number | null) ?? null,
      },
      prediction: {
        name: (pred.name as string | null) ?? '',
        estimatedLow: (pred.estimated_low as number | null) ?? 0,
        estimatedMid: (pred.estimated_mid as number | null) ?? 0,
        estimatedHigh: (pred.estimated_high as number | null) ?? 0,
        currency: (pred.currency as string | null) ?? 'EUR',
        confidence: (pred.confidence as number | null) ?? 0,
        explanation: (pred.explanation as string | null) ?? null,
      },
    };
  }

  async searchItems(query: string): Promise<Item[]> {
    if (!query.trim()) return [];

    // JOIN price_predictions via FK (item_id → items.id)
    const { data, error } = await supabase
      .from('items')
      .select('id, title, category, updated_at, attributes_json, taxonomy_version, subtype_id, collections, price_predictions(q10, q50, q90, conf_score, asof)')
      .ilike('title', `%${query}%`)
      .order('updated_at', { ascending: false })
      .limit(25);

    if (error) {
      logger.warn('[SupabaseDataProvider] searchItems error:', error);
      return [];
    }

    type PredRow = { q10: number | null; q50: number | null; q90: number | null; conf_score: number | null; asof: string | null };
    type ItemRow = {
      id: string;
      title?: string | null;
      category?: string | null;
      updated_at?: string | null;
      attributes_json?: Record<string, unknown> | null;
      taxonomy_version?: string | null;
      subtype_id?: string | null;
      collections?: string[] | null;
      price_predictions?: PredRow[];
    };

    const rows = (data ?? []) as ItemRow[];

    return rows.map((r) => {
      const preds = (r.price_predictions ?? []).sort(
        (a, b) => (b.asof ?? '').localeCompare(a.asof ?? ''),
      );
      const latest = preds[0];

      return {
        id: r.id,
        name: r.title ?? 'Untitled',
        category: r.category || 'Uncategorized',
        subtypeId: r.subtype_id ?? undefined,
        taxonomyVersion: r.taxonomy_version ?? undefined,
        collections: r.collections ?? undefined,
        attributesJson: r.attributes_json ?? undefined,
        price: latest?.q50 ?? 0,
        priceBand: latest
          ? { q10: latest.q10 ?? 0, q50: latest.q50 ?? 0, q90: latest.q90 ?? 0, confidence: latest.conf_score ?? 0, currency: 'EUR' }
          : undefined,
        imageUrl: undefined,
        updatedAt: r.updated_at ?? undefined,
      };
    });
  }

  async getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
    if (!userId) return null;

    // Check cache first (includes null for "not found" results)
    if (this.profileCache.has(userId)) {
      return this.profileCache.get(userId) ?? null;
    }

    // Query user_public_profile_v1 view (RLS: public SELECT)
    // Try user_id first (common schema), fall back to id
    let { data, error } = await supabase
      .from('user_public_profile_v1')
      .select('*')
      .eq('user_id', userId)
      .maybeSingle();

    // If no result with user_id, try id column (alternate schema)
    if (!data && !error) {
      const alt = await supabase
        .from('user_public_profile_v1')
        .select('*')
        .eq('id', userId)
        .maybeSingle();
      data = alt.data;
      error = alt.error;
    }

    if (error) {
      // No rows returned - cache null to prevent repeated lookups
      if (error.code === 'PGRST116') {
        this.profileCache.set(userId, null);
        return null;
      }
      logger.warn('[SupabaseDataProvider] getPublicUserProfile error:', error);
      // Don't cache on network/auth errors - allow retry
      return null;
    }

    if (!data) {
      this.profileCache.set(userId, null);
      return null;
    }

    // Map columns flexibly - handle various naming conventions
    const row = data as Record<string, unknown>;

    const profile: PublicUserProfile = {
      id: (row.id ?? row.user_id ?? userId) as string,
      displayName: (row.display_name ?? row.displayName ?? row.username ?? row.name ?? 'Unknown') as string,
      handle: (row.handle ?? row.username ?? null) as string | null,
      avatarUrl: (row.avatar_url ?? row.avatarUrl ?? null) as string | null,
      bio: (row.bio ?? row.about ?? row.description ?? null) as string | null,
      interests: (row.interests ?? null) as string[] | null,
      collectionCount: (row.collection_count ?? row.total_items ?? row.item_count ?? null) as number | null,
      collectionValueEur: (row.collection_value_eur ?? row.total_value_eur ?? row.portfolio_value ?? null) as number | null,
    };

    // Cache the result
    this.profileCache.set(userId, profile);
    return profile;
  }

  async getMyProfile(): Promise<PublicUserProfile | null> {
    // Return cached if already fetched
    if (this.myProfileCache !== undefined) {
      return this.myProfileCache;
    }

    // Get current user from auth
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      logger.warn('[SupabaseDataProvider] getMyProfile: not authenticated');
      this.myProfileCache = null;
      return null;
    }

    // Fetch profile using the existing method (which caches)
    const profile = await this.getPublicUserProfile(user.id);
    this.myProfileCache = profile;
    return profile;
  }

  async getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
    const category = getCategoryById(categoryId);
    if (!category) return null;

    // Fetch items matching category from Supabase
    const items = await this.searchItems(category.name.split(' ')[0]);

    // Fetch upcoming events for this category from Supabase
    const { data: eventsData } = await supabase
      .from('v_events_with_attendees_v1')
      .select('id, title, kind, date, time')
      .eq('category_id', categoryId)
      .gte('date', new Date().toISOString().split('T')[0])
      .order('date', { ascending: true })
      .limit(5);

    type EventRow = { id: string; title: string; kind: string; date: string; time?: string };
    const upcomingEvents = (eventsData ?? []).map((e: EventRow) => ({
      id: e.id,
      title: e.title,
      kind: e.kind as 'collection_drop' | 'meetup' | 'stream',
      date: e.date,
      time: e.time,
    }));

    // Return minimal data — spotlight slides and friends empty for real mode
    // These would come from dedicated tables in a full implementation
    return {
      categoryId: category.id,
      categoryName: category.name,
      categoryTagline: category.tagline,
      bannerImageUrl: category.bannerImageUrl,
      spotlightSlides: [], // Would come from category_spotlight table
      items,
      upcomingEvents,
      friendsWhoFollow: [], // Would come from user_category_follows table
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Browsing (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  async listCategorySummaries(): Promise<CategorySummary[]> {
    const { data, error } = await supabase
      .from('v_category_summaries_v1')
      .select('id, name, completion_pct, owned_count, missing_count, total_count');

    if (error) {
      logger.warn('[SupabaseDataProvider] listCategorySummaries error:', error);
      return [];
    }

    type SummaryRow = { id: string; name: string; completion_pct?: number; owned_count?: number; missing_count?: number; total_count?: number };
    return (data ?? []).map((row: SummaryRow) => ({
      id: row.id,
      name: row.name,
      completionPct: row.completion_pct ?? 0,
      ownedCount: row.owned_count ?? 0,
      missingCount: row.missing_count ?? 0,
      totalCount: row.total_count ?? 0,
    }));
  }

  async listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
    const { data, error } = await supabase
      .from('v_category_missing_items_v1')
      .select('id, category_id, title, brand, notes')
      .eq('category_id', categoryId);

    if (error) {
      logger.warn('[SupabaseDataProvider] listCategoryMissing error:', error);
      return [];
    }

    type MissingRow = { id: string; category_id: string; title: string; brand?: string; notes?: string };
    return (data ?? []).map((row: MissingRow) => ({
      id: row.id,
      categoryId: row.category_id,
      title: row.title,
      brand: row.brand,
      notes: row.notes,
    }));
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Alerts Feed (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  async listAlertsFeed(pagination?: PaginationParams): Promise<AlertFeedItem[]> {
    const limit = pagination?.limit ?? 50;
    const offset = pagination?.offset ?? 0;
    const { data, error } = await supabase
      .from('v_alerts_feed_v1')
      .select('*')
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      logger.warn('[SupabaseDataProvider] listAlertsFeed error:', error);
      return [];
    }

    if (!data) return [];

    // Map snake_case → camelCase
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

  // ─────────────────────────────────────────────────────────────────────────────
  // DM / Inbox methods
  // ─────────────────────────────────────────────────────────────────────────────

  async listInboxThreads(): Promise<DmThread[]> {
    const { data, error } = await supabase
      .from('v_chat_inbox_v1')
      .select('*')
      .order('last_message_at', { ascending: false });

    if (error) {
      logger.warn('[SupabaseDataProvider] listInboxThreads error:', error);
      return [];
    }

    if (!data) return [];

    // Map flexibly to handle various column naming conventions
    return (data as Record<string, unknown>[]).map((row) => ({
      id: (row.id ?? row.thread_id) as string,
      otherUserId: (row.other_user_id ?? row.otherUserId) as string,
      otherUserName: (row.other_user_name ?? row.otherUserName ?? 'Unknown') as string,
      otherUserHandle: (row.other_user_handle ?? row.otherUserHandle ?? null) as string | null,
      otherUserAvatarUrl: (row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null) as string | null,
      otherUserAvatarColor: (row.other_user_avatar_color ?? '#6b7280') as string,
      status: ((row.status ?? 'accepted') as string) as DmThreadStatus,
      lastMessagePreview: (row.last_message_preview ?? row.lastMessagePreview ?? null) as string | null,
      lastMessageAt: (row.last_message_at ?? row.lastMessageAt ?? null) as string | null,
      unreadCount: (row.unread_count ?? row.unreadCount ?? 0) as number,
      isIncoming: (row.is_incoming ?? row.isIncoming ?? false) as boolean,
    }));
  }

  async listIncomingRequests(): Promise<DmRequest[]> {
    const { data, error } = await supabase
      .from('v_chat_inbox_v1')
      .select('*')
      .eq('status', 'pending')
      .eq('is_incoming', true)
      .order('last_message_at', { ascending: false });

    if (error) {
      logger.warn('[SupabaseDataProvider] listIncomingRequests error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      threadId: (row.id ?? row.thread_id) as string,
      fromUserId: (row.other_user_id ?? row.otherUserId) as string,
      fromUserName: (row.other_user_name ?? row.otherUserName ?? 'Unknown') as string,
      fromUserHandle: (row.other_user_handle ?? row.otherUserHandle ?? null) as string | null,
      fromUserAvatarUrl: (row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null) as string | null,
      fromUserAvatarColor: (row.other_user_avatar_color ?? '#6b7280') as string,
      requestMessage: (row.last_message_preview ?? row.lastMessagePreview ?? null) as string | null,
      requestedAt: (row.last_message_at ?? row.lastMessageAt ?? new Date().toISOString()) as string,
    }));
  }

  async requestDm(toUserId: string, message?: string): Promise<string> {
    const { data, error } = await supabase.rpc('rpc_request_dm_v1', {
      p_to_user_id: toUserId,
      p_message: message ?? null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] requestDm error:', error);
      throw new Error(error.message || 'Failed to send DM request');
    }

    // RPC returns the thread ID
    const result = data as Record<string, unknown> | string | null;
    return (typeof result === 'object' && result !== null ? (result.thread_id as string) : result) ?? '';
  }

  async decideDmRequest(threadId: string, accept: boolean): Promise<void> {
    const { error } = await supabase.rpc('rpc_decide_dm_request_v1', {
      p_thread_id: threadId,
      p_accept: accept,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] decideDmRequest error:', error);
      throw new Error(error.message || 'Failed to process DM request');
    }
  }

  async markThreadRead(threadId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_mark_thread_read_v1', {
      p_thread_id: threadId,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] markThreadRead error:', error);
      // Don't throw - marking read is non-critical
    }
  }

  async getThreadMessages(threadId: string): Promise<DmMessage[]> {
    const { data, error } = await supabase
      .from('chat_messages_v1')
      .select('id, thread_id, author_user_id, text, created_at')
      .eq('thread_id', threadId)
      .order('created_at', { ascending: true });

    if (error) {
      logger.warn('[SupabaseDataProvider] getThreadMessages error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      id: row.id as string,
      threadId: (row.thread_id as string | null) ?? threadId,
      authorUserId: (row.author_user_id ?? row.authorUserId) as string,
      text: (row.text as string | null) ?? '',
      createdAt: (row.created_at ?? row.createdAt ?? new Date().toISOString()) as string,
    }));
  }

  async sendMessage(threadId: string, body: string): Promise<DmMessage> {
    // Writes via RPC only (per backend blueprint)
    const { data, error } = await supabase.rpc('rpc_send_message_v1', {
      p_thread_id: threadId,
      p_text: body,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] sendMessage RPC error:', error);
      throw new Error(error.message || 'Failed to send message');
    }

    // RPC may return the created message; if not, build a stub
    if (data && typeof data === 'object') {
      const row = data as Record<string, unknown>;
      return {
        id: (row.id ?? row.message_id ?? `msg-${Date.now()}`) as string,
        threadId: (row.thread_id as string | null) ?? threadId,
        authorUserId: (row.author_user_id as string | null) ?? 'current-user',
        text: (row.text as string | null) ?? body,
        createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
      };
    }

    // Fallback: return optimistic stub (caller should refresh if needed)
    return {
      id: `msg-${Date.now()}`,
      threadId,
      authorUserId: 'current-user',
      text: body,
      createdAt: new Date().toISOString(),
    };
  }

  async getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> {
    const { data, error } = await supabase
      .from('v_chat_inbox_v1')
      .select('status, is_incoming')
      .eq('other_user_id', otherUserId)
      .maybeSingle();

    if (error || !data) {
      return 'none';
    }

    const row = data as { status: string; is_incoming: boolean };
    if (row.status === 'accepted') return 'accepted';
    if (row.status === 'declined') return 'declined';
    if (row.status === 'pending') {
      return row.is_incoming ? 'pending_incoming' : 'pending_outgoing';
    }
    return 'none';
  }

  async getInboxUnreadCount(): Promise<number> {
    const { data, error } = await supabase
      .from('v_chat_inbox_v1')
      .select('unread_count, status, is_incoming');

    if (error || !data) {
      return 0;
    }

    const rows = data as { unread_count: number; status: string; is_incoming: boolean }[];

    // Sum unread from accepted threads + count pending incoming requests
    let total = 0;
    for (const row of rows) {
      if (row.status === 'accepted') {
        total += row.unread_count ?? 0;
      } else if (row.status === 'pending' && row.is_incoming) {
        total += 1; // Each pending request counts as 1
      }
    }
    return total;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Analytics
  // ─────────────────────────────────────────────────────────────────────────────

  async getAnalyticsMetrics(): Promise<AnalyticsMetrics> {
    // Initialize with zeros
    let activeProjects = 0;
    let backlogProjects = 0;
    let completedProjects = 0;
    let totalBuildMinutes = 0;
    let twitchCreatorsTracked = 0;
    let twitchCreatorsLive = 0;

    // Query all 3 tables in parallel; each can fail independently
    const [projectsRes, sessionsRes, twitchRes] = await Promise.allSettled([
      supabase.from('build_paint_projects').select('id, status').limit(500),
      supabase.from('build_paint_sessions').select('minutes').limit(2000),
      supabase.from('twitch_creators').select('id, is_live').limit(500),
    ]);

    // Build & paint projects
    if (projectsRes.status === 'fulfilled') {
      const { data, error } = projectsRes.value;
      if (!error && Array.isArray(data)) {
        for (const row of data) {
          const status = (row.status || '').toString();
          if (status === 'Active') activeProjects += 1;
          else if (status === 'Backlog') backlogProjects += 1;
          else if (status === 'Completed') completedProjects += 1;
        }
      }
    }

    // Build & paint sessions
    if (sessionsRes.status === 'fulfilled') {
      const { data, error } = sessionsRes.value;
      if (!error && Array.isArray(data)) {
        for (const row of data) {
          const m = Number(row.minutes ?? 0);
          if (!Number.isNaN(m)) totalBuildMinutes += m;
        }
      }
    }

    // Twitch creators
    if (twitchRes.status === 'fulfilled') {
      const { data, error } = twitchRes.value;
      if (!error && Array.isArray(data)) {
        twitchCreatorsTracked = data.length;
        twitchCreatorsLive = data.filter((row: { id: string; is_live?: boolean }) => row.is_live === true).length;
      }
    }

    return {
      activeProjects,
      backlogProjects,
      completedProjects,
      totalBuildMinutes,
      totalBuildHours: totalBuildMinutes / 60,
      twitchCreatorsTracked,
      twitchCreatorsLive,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Build & Paint Projects
  // ─────────────────────────────────────────────────────────────────────────────

  async listBuildPaintProjects(): Promise<BuildPaintProject[]> {
    const { data, error } = await supabase
      .from('v_build_paint_projects_v1')
      .select('id, title, category, status, percent_complete, is_completed, notes, created_at, updated_at')
      .order('updated_at', { ascending: false })
      .limit(200);

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintProjects error:', error);
      return [];
    }

    type ProjectRow = {
      id: string; title: string; category?: string; status?: string;
      percent_complete?: number; is_completed?: boolean; notes?: string;
      created_at?: string; updated_at?: string;
    };
    return (data ?? []).map((row: ProjectRow) => ({
      id: row.id,
      title: row.title,
      category: row.category,
      status: row.status,
      percent: row.percent_complete ?? 0,
      isCompleted: row.is_completed ?? false,
      notes: row.notes,
      createdAt: row.created_at ?? new Date().toISOString(),
      updatedAt: row.updated_at ?? new Date().toISOString(),
    }));
  }

  async createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
    const { data, error } = await supabase.rpc('rpc_create_build_paint_project_v1', {
      p_title: input.title,
      p_category: input.category || null,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] createBuildPaintProject error:', error);
      throw new Error(error.message || 'Failed to create project');
    }

    const row = data as Record<string, unknown>;
    return {
      id: row.id as string,
      title: row.title as string,
      category: row.category as string | undefined,
      status: row.status as string | undefined,
      percent: (row.percent_complete as number | null) ?? 0,
      isCompleted: (row.is_completed as boolean | null) ?? false,
      notes: (row.notes as string | null) || null,
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
      updatedAt: (row.updated_at as string | null) ?? new Date().toISOString(),
    };
  }

  async setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_set_build_paint_progress_v1', {
      p_project_id: projectId,
      p_percent: percent,
      p_status: status || null,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] setBuildPaintProgress error:', error);
      throw new Error(error.message || 'Failed to set progress');
    }
  }

  async markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
    const { error } = await supabase.rpc('rpc_mark_build_paint_project_complete_v1', {
      p_project_id: projectId,
      p_is_completed: isCompleted,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] markBuildPaintProjectComplete error:', error);
      throw new Error(error.message || 'Failed to mark complete');
    }
  }

  async listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]> {
    const { data, error } = await supabase
      .from('v_build_paint_project_steps_v1')
      .select('id, project_id, title, is_done, sort_order, created_at')
      .eq('project_id', projectId)
      .order('sort_order', { ascending: true });

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintSteps error:', error);
      return [];
    }

    type StepRow = { id: string; project_id: string; title: string; is_done?: boolean; sort_order?: number; created_at?: string };
    return (data ?? []).map((row: StepRow) => ({
      id: row.id,
      projectId: row.project_id,
      title: row.title,
      isDone: row.is_done ?? false,
      sortOrder: row.sort_order ?? 0,
      createdAt: row.created_at ?? new Date().toISOString(),
    }));
  }

  async addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep> {
    const { data, error } = await supabase.rpc('rpc_add_build_paint_step_v1', {
      p_project_id: projectId,
      p_title: title,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] addBuildPaintStep error:', error);
      throw new Error(error.message || 'Failed to add step');
    }

    const row = data as Record<string, unknown>;
    return {
      id: row.id as string,
      projectId: row.project_id as string,
      title: row.title as string,
      isDone: (row.is_done as boolean | null) ?? false,
      sortOrder: (row.sort_order as number | null) ?? 0,
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
    };
  }

  async toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void> {
    const { error } = await supabase.rpc('rpc_toggle_build_paint_step_v1', {
      p_step_id: stepId,
      p_is_done: isDone,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] toggleBuildPaintStep error:', error);
      throw new Error(error.message || 'Failed to toggle step');
    }
  }

  async listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]> {
    const { data, error } = await supabase
      .from('v_build_paint_project_notes_v1')
      .select('id, project_id, body, created_at')
      .eq('project_id', projectId)
      .order('created_at', { ascending: false });

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintNotes error:', error);
      return [];
    }

    type NoteRow = { id: string; project_id: string; body: string; created_at?: string };
    return (data ?? []).map((row: NoteRow) => ({
      id: row.id,
      projectId: row.project_id,
      body: row.body,
      createdAt: row.created_at ?? new Date().toISOString(),
    }));
  }

  async addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote> {
    const { data, error } = await supabase.rpc('rpc_add_build_paint_note_v1', {
      p_project_id: projectId,
      p_body: body,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] addBuildPaintNote error:', error);
      throw new Error(error.message || 'Failed to add note');
    }

    const row = data as Record<string, unknown>;
    return {
      id: row.id as string,
      projectId: row.project_id as string,
      body: row.body as string,
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Feedback
  // ─────────────────────────────────────────────────────────────────────────────

  async submitFeedback(
    itemId: string,
    feedbackType: 'sale_price' | 'disagree' | 'accurate',
    value?: string,
  ): Promise<{ success: boolean; feedbackId?: string }> {
    try {
      const res = await collectorsApi.submitFeedback({
        item_id: itemId,
        feedback_type: feedbackType,
        value,
      }) as Record<string, unknown>;
      return {
        success: (res.success as boolean | undefined) ?? true,
        feedbackId: res.feedback_id as string | undefined,
      };
    } catch (err: unknown) {
      logger.error('[SupabaseDataProvider] submitFeedback error:', err);
      throw new Error(err instanceof Error ? err.message : 'Failed to submit feedback');
    }
  }

  async submitCorrection(
    itemId: string,
    corrections: {
      correctedPrice?: number;
      correctedCondition?: string;
      correctedCategory?: string;
      notes?: string;
    },
  ): Promise<{ success: boolean }> {
    try {
      const res = await collectorsApi.submitCorrection({
        item_id: itemId,
        corrected_price: corrections.correctedPrice,
        corrected_condition: corrections.correctedCondition,
        corrected_category: corrections.correctedCategory,
        notes: corrections.notes,
      }) as Record<string, unknown>;
      return { success: (res.success as boolean | undefined) ?? true };
    } catch (err: unknown) {
      logger.error('[SupabaseDataProvider] submitCorrection error:', err);
      throw new Error(err instanceof Error ? err.message : 'Failed to submit correction');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Ownership
  // ─────────────────────────────────────────────────────────────────────────────

  async markCategoryItemOwned(
    categoryItemId: string,
    quantity: number = 1,
    notes?: string,
  ): Promise<{ success: boolean }> {
    const { error } = await supabase.rpc('rpc_mark_category_item_owned_v1', {
      p_category_item_id: categoryItemId,
      p_quantity: quantity,
      p_notes: notes ?? null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] markCategoryItemOwned error:', error);
      throw new Error(error.message || 'Failed to mark item as owned');
    }

    return { success: true };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Watchlist → Portfolio Conversion
  // ─────────────────────────────────────────────────────────────────────────────

  async convertWatchlistToItem(
    watchlistItemId: string,
    actualPrice?: number,
    notes?: string,
  ): Promise<Item> {
    // Call RPC to convert watchlist item to portfolio item
    // The RPC should: 1) create the item, 2) remove from watchlist, 3) return the new item
    const { data, error } = await supabase.rpc('rpc_convert_watchlist_to_item_v1', {
      p_watchlist_item_id: watchlistItemId,
      p_actual_price: actualPrice ?? null,
      p_notes: notes ?? null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] convertWatchlistToItem error:', error);
      throw new Error(error.message || 'Failed to convert watchlist item');
    }

    const row = data as Record<string, unknown>;
    return {
      id: row.id as string,
      name: ((row.name ?? row.title) as string | null) ?? 'Untitled',
      category: (row.category as string | null) ?? 'Other',
      price: (row.price as number | null) ?? actualPrice ?? 0,
      imageUrl: (row.image_url as string | null) ?? undefined,
      updatedAt: (row.updated_at as string | null) ?? new Date().toISOString(),
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Following
  // ─────────────────────────────────────────────────────────────────────────────

  async followCategory(categoryId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_follow_category_v1', {
      p_category_id: categoryId,
    });
    if (error) {
      logger.error('[SupabaseDataProvider] followCategory error:', error);
      throw new Error(error.message || 'Failed to follow category');
    }
  }

  async unfollowCategory(categoryId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_unfollow_category_v1', {
      p_category_id: categoryId,
    });
    if (error) {
      logger.error('[SupabaseDataProvider] unfollowCategory error:', error);
      throw new Error(error.message || 'Failed to unfollow category');
    }
  }

  async listFollowedCategories(): Promise<string[]> {
    const { data, error } = await supabase.rpc('rpc_list_followed_categories_v1');
    if (error) {
      logger.warn('[SupabaseDataProvider] listFollowedCategories error:', error);
      return [];
    }
    return (data ?? []).map((row: { category_id: string }) => row.category_id);
  }

  async isFollowingCategory(categoryId: string): Promise<boolean> {
    const { data, error } = await supabase.rpc('rpc_is_following_category_v1', {
      p_category_id: categoryId,
    });
    if (error) {
      logger.warn('[SupabaseDataProvider] isFollowingCategory error:', error);
      return false;
    }
    return data === true;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────────

  async getEventById(eventId: string): Promise<CollectorsEvent | null> {
    const { data, error } = await supabase
      .from('v_events_with_attendees_v1')
      .select('*')
      .eq('id', eventId)
      .maybeSingle();

    if (error || !data) {
      logger.warn('[SupabaseDataProvider] getEventById error:', error);
      return null;
    }

    return this.mapEventRow(data);
  }

  async listEvents(pagination?: PaginationParams): Promise<CollectorsEvent[]> {
    const limit = pagination?.limit ?? 50;
    const offset = pagination?.offset ?? 0;
    // Use personalized RPC that filters to user's categories + followed categories
    const { data, error } = await supabase.rpc('rpc_list_personalized_events_v1', {
      p_limit: limit,
      p_offset: offset,
    });

    if (error) {
      logger.warn('[SupabaseDataProvider] listEvents error:', error);
      return [];
    }

    return (data ?? []).map((row: Record<string, unknown>) => this.mapEventRow(row));
  }

  async createEvent(input: CreateEventInput): Promise<CollectorsEvent> {
    const { data, error } = await supabase.rpc('rpc_create_event_v1', {
      p_title: input.title,
      p_kind: input.kind,
      p_category_id: input.categoryId ?? null,
      p_date: input.date,
      p_time: input.time ?? null,
      p_end_date: input.endDate ?? null,
      p_location: input.location ?? null,
      p_online_url: input.onlineUrl ?? null,
      p_description: input.description,
      p_format: input.format ?? null,
      p_is_public: input.isPublic ?? null,
      p_latitude: input.latitude ?? null,
      p_longitude: input.longitude ?? null,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] createEvent error:', error);
      throw new Error(error.message || 'Failed to create event');
    }

    return this.mapEventRow(data);
  }

  async rsvpEvent(eventId: string, status: string = 'going'): Promise<void> {
    const { error } = await supabase.rpc('rpc_rsvp_event_v1', {
      p_event_id: eventId,
      p_status: status,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] rsvpEvent error:', error);
      throw new Error(error.message || 'Failed to RSVP');
    }
  }

  async unrsvpEvent(eventId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_unrsvp_event_v1', {
      p_event_id: eventId,
    });

    if (error) {
      logger.error('[SupabaseDataProvider] unrsvpEvent error:', error);
      throw new Error(error.message || 'Failed to un-RSVP');
    }
  }

  async shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
    // 1. Fetch event details
    const event = await this.getEventById(eventId);
    if (!event) {
      throw new Error(`Event not found: ${eventId}`);
    }

    // 2. Find or create a DM thread with the recipient
    const dmStatus = await this.getDmStatus(recipientUserId);
    let threadId: string;

    if (dmStatus === 'accepted') {
      // Find the existing accepted thread
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
      // Create a new DM request (thread) with the recipient
      threadId = await this.requestDm(recipientUserId);
    } else {
      throw new Error(`Cannot share event: DM status with user is "${dmStatus}"`);
    }

    // 3. Build the share message
    const message =
      `\u{1F3AB} Check out this event: ${event.title}\n` +
      `\u{1F4C5} ${event.date}${event.time ? ' ' + event.time : ''}\n` +
      `\u{1F449} collectai://events/${eventId}`;

    // 4. Send the message
    await this.sendMessage(threadId, message);
  }

  // Helper to map DB row to CollectorsEvent
  private mapEventRow(row: Record<string, unknown>): CollectorsEvent {
    return {
      id: row.id as string,
      title: row.title as string,
      kind: row.kind as CollectorsEvent['kind'],
      date: row.date as string,
      time: (row.time as string | null) ?? undefined,
      endDate: (row.end_date as string | null) ?? undefined,
      location: (row.location as string | null) ?? undefined,
      onlineUrl: (row.online_url as string | null) ?? undefined,
      description: (row.description as string | null) ?? '',
      categoryId: (row.category_id as string | null) ?? undefined,
      hostUserId: (row.created_by as string | null) ?? undefined,
      attendeeIds: [],
      attendeeCount: (row.attendee_count as number | null) ?? 0,
      isAttending: (row.is_attending as boolean | null) ?? false,
      myRsvpStatus: (row.my_rsvp_status as string | null) ?? undefined,
      source: (row.source as string | null) ?? undefined,
      sourceUrl: (row.source_url as string | null) ?? undefined,
      imageUrl: (row.image_url as string | null) ?? undefined,
      createdBy: (row.created_by as string | null) ?? undefined,
      format: (row.format as CollectorsEvent['format']) ?? undefined,
      isPublic: (row.is_public as boolean | null) ?? undefined,
      latitude: (row.latitude as number | null) ?? undefined,
      longitude: (row.longitude as number | null) ?? undefined,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Barcode / Market Data
  // ─────────────────────────────────────────────────────────────────────────────

  async lookupByBarcode(
    barcode: string,
    opts?: { codeType?: string },
  ): Promise<BarcodeLookupResult> {
    logger.info('[SupabaseDataProvider] lookupByBarcode', { barcode, opts });

    // Call backend API for barcode lookup
    // This will query product databases (Open Library, Google Books, etc.)
    // and market sources for pricing
    try {
      const res = await collectorsApi.lookupByBarcode(barcode, opts?.codeType) as Record<string, unknown>;

      const priceBandRaw = res.price_band as Record<string, unknown> | null | undefined;
      return {
        title: (res.title as string | null) ?? null,
        categoryId: (res.category_id ?? res.categoryId) as string | null ?? null,
        subtypeId: (res.subtype_id ?? res.subtypeId) as string | null ?? null,
        taxonomyVersion: (res.taxonomy_version as string | null) ?? 'v1.0',
        collections: (res.collections as string[] | null) ?? [],
        attributes: (res.attributes as Record<string, unknown> | null) ?? {},
        missingRequired: (res.missing_required as string[] | null) ?? [],
        priceBand: priceBandRaw ? {
          q10: priceBandRaw.q10 as number,
          q50: priceBandRaw.q50 as number,
          q90: priceBandRaw.q90 as number,
          confidence: priceBandRaw.confidence as number,
          currency: (priceBandRaw.currency as string | null) ?? 'EUR',
        } : null,
        rationale: (res.rationale as string[] | null) ?? [],
        barcode,
        barcodeType: opts?.codeType ?? 'unknown',
        imageUrl: (res.image_url as string | null) ?? null,
      };
    } catch (err: unknown) {
      logger.warn('[SupabaseDataProvider] lookupByBarcode API error:', err);

      // Return minimal result on error - UI can fall back to manual entry
      return {
        title: null,
        categoryId: null,
        subtypeId: null,
        taxonomyVersion: 'v1.0',
        collections: [],
        attributes: {},
        missingRequired: ['title', 'categoryId'],
        priceBand: null,
        rationale: ['Barcode lookup failed - try manual search'],
        barcode,
        barcodeType: opts?.codeType ?? 'unknown',
        imageUrl: null,
      };
    }
  }

  async marketSearch(
    query: string,
    opts?: MarketSearchOptions,
  ): Promise<MarketSearchResult> {
    logger.info('[SupabaseDataProvider] marketSearch', { query, opts });

    // Call backend API for market search
    // This aggregates results from multiple providers (eBay, TCGPlayer, etc.)
    try {
      const res = await collectorsApi.marketSearch(query, {
        category_id: opts?.categoryId,
        subtype_id: opts?.subtypeId,
        collections: opts?.collections,
        limit: opts?.limit,
        sold_only: opts?.soldOnly,
        min_price: opts?.minPrice,
        max_price: opts?.maxPrice,
      }) as Record<string, unknown>;

      return {
        hits: ((res.hits as Record<string, unknown>[] | null) ?? []).map((hit: Record<string, unknown>) => ({
          source: hit.source as string,
          rawId: (hit.raw_id ?? hit.rawId) as string,
          title: hit.title as string,
          price: hit.price as number,
          currency: (hit.currency as string | null) ?? 'EUR',
          soldAt: (hit.sold_at ?? hit.soldAt ?? null) as string | null,
          url: (hit.url ?? null) as string | null,
          condition: (hit.condition ?? null) as string | null,
          imageUrl: (hit.image_url ?? hit.imageUrl ?? null) as string | null,
          rawPayloadHash: ((hit.raw_payload_hash ?? hit.rawPayloadHash) as string | undefined) ?? undefined,
        })),
        providers: (res.providers as string[] | null) ?? [],
        totalRaw: (res.total_raw ?? res.totalRaw) as number ?? 0,
        confidence: (res.confidence as number | null) ?? 0.5,
      };
    } catch (err: unknown) {
      logger.warn('[SupabaseDataProvider] marketSearch API error:', err);

      // Return empty result on error
      return {
        hits: [],
        providers: [],
        totalRaw: 0,
        confidence: 0,
      };
    }
  }
}

// Singleton instance
export const supabaseDataProvider = new SupabaseDataProvider();
