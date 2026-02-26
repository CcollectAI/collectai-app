/**
 * SupabaseDataProvider — fetches real data from Supabase.
 * Uses the existing supabase client from src/lib/supabase.ts.
 * Returns stable shapes (no raw Supabase responses to UI).
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
import { getCategoryById } from './categories';
import logger from '../utils/logger';
import type { CollectorsEvent, CreateEventInput, EventTemplate, EventAnnouncement, SponsorCompany } from './events';
import { supabase } from '../lib/supabase';
import {
  collectorsApi,
  getUserActivity as apiGetUserActivity,
  logActivity as apiLogActivity,
  unifiedSearch as apiUnifiedSearch,
  searchEvents as apiSearchEvents,
} from '../api/collectorsApi';

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
      .select('id, title, category, updated_at, attributes_json, taxonomy_version, subtype_id, collections, images, price_predictions(q10, q50, q90, conf_score, asof)')
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
      images?: string[] | null;
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
        imageUrl: r.images?.[0] ?? undefined,
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
      currency: CurrencyCode;
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
      currency: (r.currency as CurrencyCode) || 'EUR',
      category: r.category as string | undefined,
      notes: r.notes as string | undefined,
      createdAt: r.created_at as string | undefined,
    };
  }

  async updateWatchlistItem(id: string, updates: { targetPrice?: number | null; notes?: string }): Promise<WatchlistItem> {
    const updatePayload: Record<string, unknown> = {};
    if (updates.targetPrice !== undefined) updatePayload.target_price = updates.targetPrice;
    if (updates.notes !== undefined) updatePayload.notes = updates.notes;

    const { data, error } = await supabase
      .from('watchlist')
      .update(updatePayload)
      .eq('id', id)
      .select('*')
      .single();

    if (error) {
      logger.error('[SupabaseDataProvider] updateWatchlistItem error:', error);
      throw new Error(error.message || 'Failed to update watchlist item');
    }

    const r = data as Record<string, unknown>;
    return {
      id: r.id as string,
      title: r.title as string,
      priority: (r.priority as 'low' | 'medium' | 'high') || 'medium',
      owned: (r.owned as boolean) ?? false,
      targetPrice: (r.target_price as number | null) ?? null,
      currency: (r.currency as CurrencyCode) || 'EUR',
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
    if (patch.name !== undefined) updatePayload.title = patch.name;
    if (patch.category !== undefined) updatePayload.category = patch.category;
    if (patch.imageUrl !== undefined) updatePayload.images = patch.imageUrl ? [patch.imageUrl] : [];
    // Note: price is not stored in items table — it comes from price_predictions

    const { data, error } = await supabase
      .from('items')
      .update(updatePayload)
      .eq('id', itemId)
      .select('id, title, category, updated_at, images')
      .single();

    if (error || !data) {
      logger.error('[SupabaseDataProvider] updateItem error:', error);
      throw new Error(error?.message || 'Failed to update item');
    }

    const images = (data as Record<string, unknown>).images as string[] | null;

    return {
      id: data.id,
      name: (data as Record<string, unknown>).title as string ?? 'Untitled',
      category: data.category,
      price: 0,
      imageUrl: images?.[0] ?? (data as Record<string, unknown>).image_url as string ?? undefined,
      updatedAt: (data as Record<string, unknown>).updated_at as string,
    };
  }

  async archiveItem(itemId: string): Promise<void> {
    // Try dedicated archive RPC first
    const { error } = await supabase.rpc('rpc_archive_item_v1', {
      p_item_id: itemId,
    });

    if (error) {
      // Fallback: direct attribute update to mark as archived
      logger.warn('[SupabaseDataProvider] archiveItem RPC unavailable, trying direct update:', error);
      const { data: current } = await supabase
        .from('items')
        .select('attributes_json')
        .eq('id', itemId)
        .single();

      const attrs = (current?.attributes_json as Record<string, unknown>) ?? {};
      const { error: updateError } = await supabase
        .from('items')
        .update({ attributes_json: { ...attrs, _archived: true } })
        .eq('id', itemId);

      if (updateError) {
        logger.error('[SupabaseDataProvider] archiveItem error:', updateError);
        throw new Error(updateError.message || 'Failed to archive item');
      }
    }
  }

  async unarchiveItem(itemId: string): Promise<void> {
    // Try dedicated unarchive RPC first
    const { error } = await supabase.rpc('rpc_unarchive_item_v1', {
      p_item_id: itemId,
    });

    if (error) {
      // Fallback: remove _archived flag from attributes_json
      logger.warn('[SupabaseDataProvider] unarchiveItem RPC unavailable, trying direct update:', error);
      const { data: current } = await supabase
        .from('items')
        .select('attributes_json')
        .eq('id', itemId)
        .single();

      const attrs = { ...((current?.attributes_json as Record<string, unknown>) ?? {}) };
      delete attrs._archived;
      const { error: updateError } = await supabase
        .from('items')
        .update({ attributes_json: attrs })
        .eq('id', itemId);

      if (updateError) {
        logger.error('[SupabaseDataProvider] unarchiveItem error:', updateError);
        throw new Error(updateError.message || 'Failed to unarchive item');
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

  async quickscanSingle(imageUri?: string): Promise<QuickScanResult> {
    // ── Vision pipeline path (preferred when image is available) ────────
    if (imageUri) {
      const intake = await collectorsApi.intakeImageOnly(imageUri);

      const priceBand = intake.price_band;
      const q10 = priceBand?.q10 ?? 0;
      const q50 = priceBand?.q50 ?? (intake.estimated_price ?? 0);
      const q90 = priceBand?.q90 ?? 0;
      const confidence = priceBand?.confidence ?? intake.category_confidence ?? 0;
      const currency = (priceBand?.currency as CurrencyCode) ?? 'EUR';

      // Extract condition from attributes if available
      const condition = (intake.attributes?.condition as string | undefined)
        ?? (intake.attributes?.condition_guess as string | undefined)
        ?? null;

      return {
        itemId: null,
        attributes: {
          category: intake.category_id ?? '',
          editionGuess: (intake.attributes?.edition as string | undefined) ?? null,
          conditionGuess: condition,
          rarityScore: (intake.attributes?.rarity_score as number | undefined) ?? null,
        },
        prediction: {
          name: intake.name ?? '',
          estimatedLow: q10,
          estimatedMid: q50,
          estimatedHigh: q90,
          currency,
          confidence,
          explanation: intake.rationale?.length ? intake.rationale.join(' ') : null,
        },
      };
    }

    // ── Legacy fallback (no image) ─────────────────────────────────────
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
        currency: (pred.currency as CurrencyCode | null) ?? 'EUR',
        confidence: (pred.confidence as number | null) ?? 0,
        explanation: (pred.explanation as string | null) ?? null,
      },
    };
  }

  async searchItems(query: string): Promise<Item[]> {
    if (!query.trim()) return [];

    // Escape LIKE metacharacters to prevent pattern injection
    const escaped = query.replace(/%/g, '\\%').replace(/_/g, '\\_');

    // JOIN price_predictions via FK (item_id → items.id)
    const { data, error } = await supabase
      .from('items')
      .select('id, title, category, updated_at, attributes_json, taxonomy_version, subtype_id, collections, images, price_predictions(q10, q50, q90, conf_score, asof)')
      .ilike('title', `%${escaped}%`)
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
      images?: string[] | null;
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
        imageUrl: r.images?.[0] ?? undefined,
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

    // Fetch items matching category directly by category_id
    const { data: itemsData } = await supabase
      .from('items')
      .select('id, title, category, updated_at, images')
      .eq('category', categoryId)
      .order('updated_at', { ascending: false })
      .limit(20);

    type CatItemRow = { id: string; title?: string | null; category?: string | null; updated_at?: string | null; images?: string[] | null };
    const items: Item[] = (itemsData ?? []).map((r: CatItemRow) => ({
      id: r.id,
      name: r.title ?? 'Untitled',
      category: r.category ?? categoryId,
      price: 0,
      imageUrl: r.images?.[0] ?? undefined,
      updatedAt: r.updated_at ?? new Date().toISOString(),
    }));

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
      .select('id, thread_id, author_user_id, text, created_at, read_at')
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
      readAt: (row.read_at as string | null) ?? null,
    }));
  }

  async sendMessage(threadId: string, body: string): Promise<DmMessage> {
    // Get current user ID for the response
    const { data: { user } } = await supabase.auth.getUser();
    const currentUserId = user?.id ?? 'unknown';

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
        authorUserId: (row.author_user_id as string | null) ?? currentUserId,
        text: (row.text as string | null) ?? body,
        createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
      };
    }

    // Fallback: return optimistic stub (caller should refresh if needed)
    return {
      id: `msg-${Date.now()}`,
      threadId,
      authorUserId: currentUserId,
      text: body,
      createdAt: new Date().toISOString(),
    };
  }

  async setTyping(threadId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_set_typing_v1', {
      p_thread_id: threadId,
    });
    if (error) {
      logger.warn('[SupabaseDataProvider] setTyping error:', error);
    }
  }

  async clearTyping(threadId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_clear_typing_v1', {
      p_thread_id: threadId,
    });
    if (error) {
      logger.warn('[SupabaseDataProvider] clearTyping error:', error);
    }
  }

  async isOtherUserTyping(threadId: string): Promise<boolean> {
    const { data, error } = await supabase.rpc('rpc_get_typing_v1', {
      p_thread_id: threadId,
    });
    if (error || !data) return false;
    const rows = data as { user_id: string; is_typing: boolean }[];
    return rows.some((r) => r.is_typing);
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
    // Try view first, then fall back to base table for paint_recipes
    const { data, error } = await supabase
      .from('build_paint_projects')
      .select('*')
      .order('updated_at', { ascending: false })
      .limit(200);

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintProjects error:', error);
      return [];
    }

    return (data ?? []).map((row: Record<string, unknown>) => ({
      id: row.id as string,
      title: (row.title as string) || 'Untitled',
      category: row.category as string | undefined,
      categoryId: (row.category_id as string) ?? undefined,
      itemId: (row.item_id as string) ?? undefined,
      itemName: (row.item_name as string) ?? undefined,
      itemImageUrl: (row.item_images as string[])?.[0] ?? undefined,
      status: row.status as string | undefined,
      percent: (row.percent_complete as number) ?? 0,
      isCompleted: (row.is_completed as boolean) ?? false,
      notes: row.notes as string | undefined,
      imageUrl: (row.image_url as string) ?? undefined,
      paintRecipes: (row.paint_recipes as PaintRecipe[]) ?? [],
      createdAt: (row.created_at as string) ?? new Date().toISOString(),
      updatedAt: (row.updated_at as string) ?? new Date().toISOString(),
    }));
  }

  async createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
    // Try with extended params first, fall back to original 2-param RPC
    let data: unknown;
    let error: { message?: string } | null;

    ({ data, error } = await supabase.rpc('rpc_create_build_paint_project_v1', {
      p_title: input.title,
      p_category: input.category || null,
      p_category_id: input.categoryId || null,
      p_item_id: input.itemId || null,
    }));

    // Fall back to original RPC signature if extra params not supported
    if (error) {
      logger.info('[SupabaseDataProvider] trying original RPC signature');
      ({ data, error } = await supabase.rpc('rpc_create_build_paint_project_v1', {
        p_title: input.title,
        p_category: input.category || null,
      }));
    }

    if (error) {
      logger.warn('[SupabaseDataProvider] createBuildPaintProject error:', error);
      throw new Error(error.message || 'Failed to create project');
    }

    const row = data as Record<string, unknown>;
    return {
      id: row.id as string,
      title: row.title as string,
      category: row.category as string | undefined,
      categoryId: (row.category_id as string | null) ?? undefined,
      itemId: (row.item_id as string | null) ?? undefined,
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

  async listBuildPaintProjectsByCategory(categoryId: string): Promise<BuildPaintProject[]> {
    const { data, error } = await supabase
      .from('build_paint_projects')
      .select('*')
      .eq('category_id', categoryId)
      .order('updated_at', { ascending: false });

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintProjectsByCategory error:', error);
      return [];
    }

    return (data ?? []).map((r: Record<string, unknown>) => ({
      id: r.id as string,
      title: (r.name as string) ?? 'Untitled',
      status: (r.status as string) ?? 'in_progress',
      categoryId: (r.category_id as string | null) ?? undefined,
      itemId: (r.item_id as string | null) ?? undefined,
      imageUrl: (r.cover_image_url as string | null) ?? undefined,
      percent: 0,
      isCompleted: (r.status as string) === 'completed',
      paintRecipes: (r.paint_recipes as PaintRecipe[]) ?? [],
      createdAt: (r.created_at as string | null) ?? new Date().toISOString(),
      updatedAt: (r.updated_at as string | null) ?? new Date().toISOString(),
    }));
  }

  async listBuildPaintProjectsByItem(itemId: string): Promise<BuildPaintProject[]> {
    const { data, error } = await supabase
      .from('build_paint_projects')
      .select('*')
      .eq('item_id', itemId)
      .order('updated_at', { ascending: false });

    if (error) {
      logger.warn('[SupabaseDataProvider] listBuildPaintProjectsByItem error:', error);
      return [];
    }

    return (data ?? []).map((r: Record<string, unknown>) => ({
      id: r.id as string,
      title: (r.name as string) ?? 'Untitled',
      status: (r.status as string) ?? 'in_progress',
      categoryId: (r.category_id as string | null) ?? undefined,
      itemId: (r.item_id as string | null) ?? undefined,
      imageUrl: (r.cover_image_url as string | null) ?? undefined,
      percent: 0,
      isCompleted: (r.status as string) === 'completed',
      paintRecipes: (r.paint_recipes as PaintRecipe[]) ?? [],
      createdAt: (r.created_at as string | null) ?? new Date().toISOString(),
      updatedAt: (r.updated_at as string | null) ?? new Date().toISOString(),
    }));
  }

  async applyStepTemplate(projectId: string, categoryId: string): Promise<BuildPaintStep[]> {
    const { getStepTemplateForCategory } = await import('../constants/buildStepTemplates');
    const template = getStepTemplateForCategory(categoryId);
    const steps: BuildPaintStep[] = [];
    for (const s of template.steps) {
      const step = await this.addBuildPaintStep(projectId, s.label);
      steps.push(step);
    }
    return steps;
  }

  async updateBuildPaintProject(projectId: string, patch: { paintRecipes?: unknown[] }): Promise<void> {
    const updatePayload: Record<string, unknown> = {};
    if (patch.paintRecipes !== undefined) {
      updatePayload.paint_recipes = patch.paintRecipes;
    }
    const { error } = await supabase
      .from('build_paint_projects')
      .update(updatePayload)
      .eq('id', projectId);
    if (error) {
      logger.error('[SupabaseDataProvider] updateBuildPaintProject error:', error);
      throw new Error(error.message || 'Failed to update project');
    }
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
      goingCount: (row.going_count as number | null) ?? 0,
      interestedCount: (row.interested_count as number | null) ?? 0,
      maxAttendees: (row.max_attendees as number | null) ?? undefined,
      isFull: (row.is_full as boolean | null) ?? false,
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
      isSponsored: (row.is_sponsored as boolean | null) ?? false,
      sponsorName: (row.sponsor_name as string | null) ?? undefined,
      sponsorLogoUrl: (row.sponsor_logo_url as string | null) ?? undefined,
      sponsorTier: (row.sponsor_tier as CollectorsEvent['sponsorTier']) ?? undefined,
      sponsorCompanyId: (row.sponsor_company_id as string | null) ?? undefined,
    };
  }

  // Helper to map API response to CollectorsEvent (camelCase keys from backend)
  private mapEventApiResponse(row: Record<string, unknown>): CollectorsEvent {
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
      goingCount: (row.going_count as number | null) ?? 0,
      interestedCount: (row.interested_count as number | null) ?? 0,
      maxAttendees: (row.max_attendees as number | null) ?? undefined,
      isFull: (row.is_full as boolean | null) ?? false,
      isAttending: (row.user_rsvp_status as string | null) != null,
      myRsvpStatus: (row.user_rsvp_status as string | null) ?? undefined,
      source: (row.source as string | null) ?? undefined,
      imageUrl: (row.image_url as string | null) ?? undefined,
      createdBy: (row.created_by as string | null) ?? undefined,
      format: (row.format as CollectorsEvent['format']) ?? undefined,
      status: (row.status as CollectorsEvent['status']) ?? undefined,
      isPublic: (row.is_public as boolean | null) ?? undefined,
      latitude: (row.latitude as number | null) ?? undefined,
      longitude: (row.longitude as number | null) ?? undefined,
      isSponsored: (row.is_sponsored as boolean | null) ?? false,
      sponsorName: (row.sponsor_name as string | null) ?? undefined,
      sponsorLogoUrl: (row.sponsor_logo_url as string | null) ?? undefined,
      sponsorTier: (row.sponsor_tier as CollectorsEvent['sponsorTier']) ?? undefined,
      sponsorCompanyId: (row.sponsor_company_id as string | null) ?? undefined,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Event Host Actions
  // ─────────────────────────────────────────────────────────────────────────────

  async updateEvent(eventId: string, patch: Partial<CreateEventInput & { status?: string }>): Promise<CollectorsEvent> {
    const snakePatch: Record<string, unknown> = {};
    if (patch.title !== undefined) snakePatch.title = patch.title;
    if (patch.description !== undefined) snakePatch.description = patch.description;
    if (patch.location !== undefined) snakePatch.location = patch.location;
    if (patch.onlineUrl !== undefined) snakePatch.online_url = patch.onlineUrl;
    if (patch.imageUrl !== undefined) snakePatch.image_url = patch.imageUrl;
    if (patch.date !== undefined) snakePatch.date = patch.date;
    if (patch.time !== undefined) snakePatch.time = patch.time;
    if (patch.endDate !== undefined) snakePatch.end_date = patch.endDate;
    if (patch.format !== undefined) snakePatch.format = patch.format;
    if (patch.isPublic !== undefined) snakePatch.is_public = patch.isPublic;
    if (patch.status !== undefined) snakePatch.status = patch.status;
    if (patch.maxAttendees !== undefined) snakePatch.max_attendees = patch.maxAttendees;

    const resp = await collectorsApi.patch(`/events/${eventId}`, snakePatch);
    return this.mapEventApiResponse(resp as Record<string, unknown>);
  }

  async cancelEvent(eventId: string): Promise<void> {
    await collectorsApi.delete(`/events/${eventId}`);
  }

  async duplicateEvent(eventId: string): Promise<CollectorsEvent> {
    const resp = await collectorsApi.post(`/events/${eventId}/duplicate`);
    return this.mapEventApiResponse(resp as Record<string, unknown>);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Event Templates
  // ─────────────────────────────────────────────────────────────────────────────

  async listEventTemplates(): Promise<import('./events').EventTemplate[]> {
    const resp = await collectorsApi.get('/events/templates') as Record<string, unknown>[];
    return resp.map((r) => ({
      id: r.id as string,
      name: r.name as string,
      templateData: (r.template_data as Record<string, unknown>) ?? {},
      useCount: (r.use_count as number) ?? 0,
      createdAt: (r.created_at as string | null) ?? undefined,
    }));
  }

  async createEventTemplate(name: string, fromEventId?: string): Promise<import('./events').EventTemplate> {
    const body: Record<string, unknown> = { name };
    if (fromEventId) body.from_event_id = fromEventId;
    const r = await collectorsApi.post('/events/templates', body) as Record<string, unknown>;
    return {
      id: r.id as string,
      name: r.name as string,
      templateData: (r.template_data as Record<string, unknown>) ?? {},
      useCount: (r.use_count as number) ?? 0,
      createdAt: (r.created_at as string | null) ?? undefined,
    };
  }

  async deleteEventTemplate(templateId: string): Promise<void> {
    await collectorsApi.delete(`/events/templates/${templateId}`);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Sponsor Companies
  // ─────────────────────────────────────────────────────────────────────────────

  async registerSponsorCompany(input: {
    name: string; logoUrl?: string; websiteUrl?: string;
    contactEmail: string; description?: string;
  }): Promise<import('./events').SponsorCompany> {
    const body = {
      name: input.name,
      logo_url: input.logoUrl,
      website_url: input.websiteUrl,
      contact_email: input.contactEmail,
      description: input.description,
    };
    const r = await collectorsApi.post('/sponsor-companies', body) as Record<string, unknown>;
    return this._mapSponsorCompany(r);
  }

  async getMySponsorCompanies(): Promise<import('./events').SponsorCompany[]> {
    const resp = await collectorsApi.get('/sponsor-companies/mine') as Record<string, unknown>[];
    return resp.map((r) => this._mapSponsorCompany(r));
  }

  async updateSponsorCompany(id: string, patch: Partial<{
    name: string; logoUrl: string; websiteUrl: string;
    contactEmail: string; description: string;
  }>): Promise<import('./events').SponsorCompany> {
    const body: Record<string, unknown> = {};
    if (patch.name !== undefined) body.name = patch.name;
    if (patch.logoUrl !== undefined) body.logo_url = patch.logoUrl;
    if (patch.websiteUrl !== undefined) body.website_url = patch.websiteUrl;
    if (patch.contactEmail !== undefined) body.contact_email = patch.contactEmail;
    if (patch.description !== undefined) body.description = patch.description;
    const r = await collectorsApi.patch(`/sponsor-companies/${id}`, body) as Record<string, unknown>;
    return this._mapSponsorCompany(r);
  }

  async createSponsorEventCheckout(companyId: string, tier: string, eventData: CreateEventInput) {
    const body = {
      tier,
      event_title: eventData.title,
      event_kind: eventData.kind,
      event_category_id: eventData.categoryId,
      event_date: eventData.date,
      event_time: eventData.time,
      event_end_date: eventData.endDate,
      event_location: eventData.location,
      event_online_url: eventData.onlineUrl,
      event_description: eventData.description,
      event_image_url: eventData.imageUrl,
      event_format: eventData.format,
      event_max_attendees: eventData.maxAttendees,
    };
    const r = await collectorsApi.post(`/sponsor-companies/${companyId}/create-event-checkout`, body) as Record<string, unknown>;
    return {
      url: r.url as string,
      sessionId: r.session_id as string,
      eventId: r.event_id as string,
    };
  }

  private _mapSponsorCompany(r: Record<string, unknown>): import('./events').SponsorCompany {
    return {
      id: r.id as string,
      name: r.name as string,
      logoUrl: (r.logo_url as string | null) ?? undefined,
      websiteUrl: (r.website_url as string | null) ?? undefined,
      contactEmail: r.contact_email as string,
      description: (r.description as string | null) ?? undefined,
      adminUserId: r.admin_user_id as string,
      isVerified: (r.is_verified as boolean) ?? false,
      createdAt: (r.created_at as string | null) ?? undefined,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Event Announcements
  // ─────────────────────────────────────────────────────────────────────────────

  async listEventAnnouncements(eventId: string): Promise<import('./events').EventAnnouncement[]> {
    const resp = await collectorsApi.get(`/events/${eventId}/announcements`) as Record<string, unknown>[];
    return resp.map((r) => ({
      id: r.id as string,
      eventId: r.event_id as string,
      authorUserId: r.author_user_id as string,
      title: (r.title as string | null) ?? undefined,
      body: r.body as string,
      imageUrl: (r.image_url as string | null) ?? undefined,
      isRead: (r.is_read as boolean) ?? false,
      createdAt: (r.created_at as string | null) ?? undefined,
    }));
  }

  async postEventAnnouncement(eventId: string, body: string, title?: string, imageUrl?: string): Promise<import('./events').EventAnnouncement> {
    const payload: Record<string, unknown> = { body };
    if (title) payload.title = title;
    if (imageUrl) payload.image_url = imageUrl;
    const r = await collectorsApi.post(`/events/${eventId}/announcements`, payload) as Record<string, unknown>;
    return {
      id: r.id as string,
      eventId: r.event_id as string,
      authorUserId: r.author_user_id as string,
      title: (r.title as string | null) ?? undefined,
      body: r.body as string,
      imageUrl: (r.image_url as string | null) ?? undefined,
      isRead: false,
      createdAt: (r.created_at as string | null) ?? undefined,
    };
  }

  async markAnnouncementRead(eventId: string, announcementId: string): Promise<void> {
    await collectorsApi.post(`/events/${eventId}/announcements/${announcementId}/read`);
  }

  async getUnreadAnnouncementCount(): Promise<number> {
    const r = await collectorsApi.get('/events/my-announcements/unread-count') as Record<string, unknown>;
    return (r.unread_count as number) ?? 0;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Deep Dive Analytics
  // ─────────────────────────────────────────────────────────────────────────────

  async getCategoryDeepDive(categoryId: string, days?: number): Promise<Record<string, unknown>> {
    const params = days ? `?days=${days}` : '';
    return await collectorsApi.get(`/analytics/categories/${categoryId}/deep-dive${params}`) as Record<string, unknown>;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // User Search
  // ─────────────────────────────────────────────────────────────────────────────

  async searchUsers(query: string): Promise<PublicUserProfile[]> {
    if (!query.trim()) return [];

    const pattern = `%${query.trim()}%`;

    // Search by display_name OR handle using case-insensitive ILIKE via .or()
    const { data, error } = await supabase
      .from('user_public_profiles')
      .select('user_id, display_name, handle, avatar_url, bio, interests')
      .or(`display_name.ilike.${pattern},handle.ilike.${pattern}`)
      .limit(20);

    if (error) {
      logger.warn('[SupabaseDataProvider] searchUsers error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      id: (row.user_id ?? row.id) as string,
      displayName: (row.display_name as string | null) ?? 'Unknown',
      handle: (row.handle as string | null) ?? null,
      avatarUrl: (row.avatar_url as string | null) ?? null,
      bio: (row.bio as string | null) ?? null,
      interests: (row.interests as string[] | null) ?? null,
    }));
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // User Blocking
  // ─────────────────────────────────────────────────────────────────────────────

  async blockUser(userId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_block_user_v1', {
      p_target_id: userId,
    });
    if (error) {
      logger.error('[SupabaseDataProvider] blockUser error:', error);
      throw new Error(error.message || 'Failed to block user');
    }
  }

  async unblockUser(userId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_unblock_user_v1', {
      p_target_id: userId,
    });
    if (error) {
      logger.error('[SupabaseDataProvider] unblockUser error:', error);
      throw new Error(error.message || 'Failed to unblock user');
    }
  }

  async listBlockedUsers(): Promise<{ id: string; name: string }[]> {
    const { data, error } = await supabase.rpc('rpc_list_blocked_v1');
    if (error) {
      logger.warn('[SupabaseDataProvider] listBlockedUsers error:', error);
      return [];
    }

    const rows = (data ?? []) as { blocked_id: string }[];

    // Fetch profiles in parallel instead of sequential loop
    const settled = await Promise.allSettled(
      rows.map((row) => this.getPublicUserProfile(row.blocked_id)),
    );

    return rows.map((row, i) => {
      const result = settled[i];
      const profile = result.status === 'fulfilled' ? result.value : null;
      return {
        id: row.blocked_id,
        name: (profile as { displayName?: string } | null)?.displayName ?? 'Unknown',
      };
    });
  }

  async isBlocked(userId: string): Promise<boolean> {
    const { data, error } = await supabase.rpc('rpc_is_blocked_v1', {
      p_other_id: userId,
    });
    if (error) {
      logger.warn('[SupabaseDataProvider] isBlocked error:', error);
      return false;
    }
    return data === true;
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
          currency: (priceBandRaw.currency as CurrencyCode | null) ?? 'EUR',
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
          currency: (hit.currency as CurrencyCode | null) ?? 'EUR',
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
  // ─── Presence ───────────────────────────────────────────────────────────────

  async sendHeartbeat(): Promise<void> {
    try {
      await supabase.rpc('rpc_heartbeat_v1');
    } catch (err: unknown) {
      logger.warn('[SupabaseDataProvider] heartbeat error:', err);
    }
  }

  async goOffline(): Promise<void> {
    try {
      await supabase.rpc('rpc_go_offline_v1');
    } catch (err: unknown) {
      logger.warn('[SupabaseDataProvider] goOffline error:', err);
    }
  }

  async getUserPresence(userId: string): Promise<import('./types').UserPresence | null> {
    try {
      const { data } = await supabase.rpc('rpc_get_presence_v1', { p_user_id: userId });
      if (!data || (Array.isArray(data) && data.length === 0)) return null;
      const row = Array.isArray(data) ? data[0] : data;
      return {
        userId: row.user_id,
        lastSeenAt: row.last_seen_at,
        isOnline: row.is_online,
      };
    } catch {
      return null;
    }
  }

  async getBatchPresence(userIds: string[]): Promise<import('./types').UserPresence[]> {
    try {
      const { data } = await supabase.rpc('rpc_get_batch_presence_v1', { p_user_ids: userIds });
      return (data || []).map((row: Record<string, unknown>) => ({
        userId: row.user_id as string,
        lastSeenAt: row.last_seen_at as string,
        isOnline: row.is_online as boolean,
      }));
    } catch {
      return [];
    }
  }

  // ─── Activity Feed ─────────────────────────────────────────────────────────

  async getUserActivity(userId: string, limit = 20, offset = 0): Promise<import('./types').ActivityFeedItem[]> {
    try {
      const resp = await apiGetUserActivity(userId, limit, offset) as Record<string, unknown>;
      return ((resp.activities as Record<string, unknown>[]) || []).map((a) => ({
        id: a.id as string,
        userId: a.user_id as string,
        activityType: a.activity_type as import('./types').ActivityType,
        title: a.title as string,
        description: (a.description as string | null) ?? null,
        metadata: (a.metadata as Record<string, unknown>) || {},
        isPublic: a.is_public as boolean,
        createdAt: a.created_at as string,
      }));
    } catch {
      return [];
    }
  }

  async logActivity(activityType: string, title: string, description?: string, metadata?: Record<string, unknown>, isPublic = true): Promise<void> {
    try {
      await apiLogActivity({
        activity_type: activityType,
        title,
        description,
        metadata: metadata || {},
        is_public: isPublic,
      });
    } catch (err: unknown) {
      logger.warn('[SupabaseDataProvider] logActivity error:', err);
    }
  }

  // ─── Unified Search ────────────────────────────────────────────────────────

  async unifiedSearch(query: string, limit = 5) {
    try {
      const resp = await apiUnifiedSearch(query, limit) as Record<string, unknown>;
      return {
        items: ((resp.items as Record<string, unknown>[]) || []).map((i) => ({
          id: i.id as string,
          name: i.name as string,
          category: i.category as string,
          imageUrl: (i.image_url ?? i.imageUrl ?? null) as string | null,
          price: i.price as number | undefined,
        })),
        catalog: ((resp.catalog as Record<string, unknown>[]) || []).map((c) => ({
          id: c.id as string,
          category: c.category as string,
          itemKey: (c.item_key ?? c.itemKey) as string,
          title: c.title as string,
          brand: (c.brand ?? null) as string | null,
          imageUrl: (c.image_url ?? c.imageUrl ?? null) as string | null,
        })),
        users: ((resp.users as Record<string, unknown>[]) || []).map((u) => ({
          id: u.id as string,
          displayName: (u.display_name ?? u.displayName) as string,
          handle: u.handle as string | undefined,
          avatarUrl: (u.avatar_url ?? u.avatarUrl ?? null) as string | null,
        })),
        events: ((resp.events as Record<string, unknown>[]) || []).map((e) => ({
          id: e.id as string,
          title: e.title as string,
          startDate: (e.start_date ?? e.startDate) as string | undefined,
          location: e.location as string | undefined,
          category: e.category as string | undefined,
        })),
        categories: (resp.categories as Array<{ id: string; name: string }>) || [],
      };
    } catch {
      return { items: [], catalog: [], users: [], events: [], categories: [] };
    }
  }

  // ─── Event Search ──────────────────────────────────────────────────────────

  async searchEvents(params: {
    q?: string;
    category?: string;
    eventType?: string;
    location?: string;
    upcomingOnly?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<import('./events').CollectorsEvent[]> {
    try {
      const resp = await apiSearchEvents(params) as Record<string, unknown>;
      return ((resp.events as Record<string, unknown>[]) || []).map((e) => ({
        id: e.id as string,
        title: e.title as string,
        description: (e.description ?? '') as string,
        kind: (e.event_type ?? e.eventType ?? e.kind ?? 'meetup') as string,
        date: (e.start_date ?? e.startDate ?? e.date ?? '') as string,
        endDate: (e.end_date ?? e.endDate ?? undefined) as string | undefined,
        location: (e.location ?? '') as string,
        categoryId: (e.category ?? e.categoryId ?? undefined) as string | undefined,
        hostUserId: (e.organizer_id ?? e.organizerId ?? undefined) as string | undefined,
        attendeeIds: [],
        attendeeCount: (e.attendee_count ?? e.attendeeCount ?? 0) as number,
        interestedCount: (e.interested_count ?? e.interestedCount ?? 0) as number,
        maxAttendees: (e.max_attendees ?? e.maxAttendees ?? null) as number | null,
        isAttending: false,
      })) as import('./events').CollectorsEvent[];
    } catch {
      return [];
    }
  }

  // ─── Deal Desk (P2P Offers) ───────────────────────────────────────────────

  async proposeOffer(itemId: string, price: number, message?: string): Promise<Offer> {
    return collectorsApi.proposeOffer({ item_id: itemId, price, message }) as Promise<Offer>;
  }

  async counterOffer(offerId: string, price: number, message?: string): Promise<Offer> {
    return collectorsApi.counterOffer(offerId, { price, message }) as Promise<Offer>;
  }

  async respondToOffer(offerId: string, accept: boolean, message?: string): Promise<void> {
    await collectorsApi.respondToOffer(offerId, { accept, message });
  }

  async cancelOffer(offerId: string): Promise<void> {
    await collectorsApi.cancelOffer(offerId);
  }

  async listActiveOffers(): Promise<Offer[]> {
    const result = await collectorsApi.listActiveOffers() as { offers?: Offer[]; total_count?: number } | Offer[];
    return Array.isArray(result) ? result : (result?.offers ?? []);
  }

  async listDealHistory(): Promise<Offer[]> {
    const result = await collectorsApi.listDealHistory() as { offers?: Offer[]; total_count?: number } | Offer[];
    return Array.isArray(result) ? result : (result?.offers ?? []);
  }

  async getOfferDetail(offerId: string): Promise<{ offer: Offer; events: OfferEvent[] }> {
    return collectorsApi.getOfferDetail(offerId) as Promise<{ offer: Offer; events: OfferEvent[] }>;
  }

  async getUserReputation(userId: string): Promise<UserReputation> {
    return collectorsApi.getUserReputation(userId) as Promise<UserReputation>;
  }

  async toggleForSale(itemId: string, forSale: boolean, askingPrice?: number): Promise<void> {
    await collectorsApi.toggleItemForSale(itemId, { for_sale: forSale, asking_price: askingPrice });
  }

  async markShipped(offerId: string, trackingInfo?: string): Promise<void> {
    await collectorsApi.markShipped(offerId, { tracking_info: trackingInfo });
  }

  async completeDeal(offerId: string, stars: number, comment?: string): Promise<void> {
    await collectorsApi.completeDeal(offerId, { stars, comment });
  }
}

// Singleton instance
export const supabaseDataProvider = new SupabaseDataProvider();
