/**
 * SupabaseDataProvider — fetches real data from Supabase.
 * Uses the existing supabase client from src/lib/supabase.ts.
 * Returns stable shapes (no raw Supabase responses to UI).
 */

import type { DataProvider } from './DataProvider';
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
  DmThreadStatus,
  AnalyticsMetrics,
} from './types';
import { getCategoryById } from './categories';
import { EVENTS } from './events';
import { supabase } from '../lib/supabase';
import { collectorsApi } from '../api/collectorsApi';

export class SupabaseDataProvider implements DataProvider {
  async getPortfolioSummary(): Promise<PortfolioSummary> {
    // Fetch portfolio values series
    const { data: valuesData, error: valuesError } = await supabase
      .from('portfolio_values')
      .select('at,value')
      .order('at', { ascending: true })
      .limit(365);

    if (valuesError) {
      console.warn('[SupabaseDataProvider] getPortfolioSummary error:', valuesError);
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
      console.warn('[SupabaseDataProvider] item count error:', countError);
    }

    return {
      total,
      deltaPct,
      itemCount: count ?? 0,
    };
  }

  async listItems(): Promise<Item[]> {
    const { data, error } = await supabase
      .from('items')
      .select('id,title,image_url,category,value,updated_at')
      .order('updated_at', { ascending: false })
      .limit(200);

    if (error) {
      console.warn('[SupabaseDataProvider] listItems error:', error);
      return [];
    }

    const rows = (data ?? []) as {
      id: string;
      title: string;
      image_url?: string | null;
      category?: string | null;
      value?: number | null;
      updated_at?: string | null;
    }[];

    return rows.map((r) => ({
      id: r.id,
      name: r.title,
      category: r.category || 'Uncategorized',
      price: typeof r.value === 'number' ? r.value : 0,
      imageUrl: r.image_url ?? undefined,
      updatedAt: r.updated_at ?? undefined,
    }));
  }

  async listWatchlist(userId: string): Promise<WatchlistItem[]> {
    if (!userId) return [];

    const { data, error } = await supabase
      .from('watchlist_items')
      .select('id,title,priority,owned,target_price,currency')
      .eq('user_id', userId)
      .order('rank', { ascending: true, nullsFirst: true })
      .order('created_at', { ascending: true });

    if (error) {
      console.warn('[SupabaseDataProvider] listWatchlist error:', error);
      return [];
    }

    const rows = (data ?? []) as {
      id: string;
      title: string;
      priority: 'high' | 'medium' | 'low';
      owned: boolean;
      target_price: number | null;
      currency: string;
    }[];

    return rows.map((r) => ({
      id: r.id,
      title: r.title,
      priority: r.priority,
      owned: r.owned,
      targetPrice: r.target_price,
      currency: r.currency,
    }));
  }

  async createItem(input: CreateItemInput): Promise<Item> {
    const { data, error } = await supabase
      .from('items')
      .insert({
        title: input.name,
        category: input.category,
        value: input.price,
        image_url: input.imageUrl ?? null,
      })
      .select('id,title,image_url,category,value,updated_at')
      .single();

    if (error) {
      console.error('[SupabaseDataProvider] createItem error:', error);
      throw new Error(error.message || 'Failed to create item');
    }

    const r = data as {
      id: string;
      title: string;
      image_url?: string | null;
      category?: string | null;
      value?: number | null;
      updated_at?: string | null;
    };

    return {
      id: r.id,
      name: r.title,
      category: r.category || 'Uncategorized',
      price: typeof r.value === 'number' ? r.value : 0,
      imageUrl: r.image_url ?? undefined,
      updatedAt: r.updated_at ?? undefined,
    };
  }

  async quickscanSingle(): Promise<QuickScanResult> {
    // Call HTTP endpoint via collectorsApi
    const res = await collectorsApi.quickscanSingle();

    // Map snake_case response to camelCase
    return {
      itemId: res.item_id ?? null,
      attributes: {
        category: res.attributes?.category ?? '',
        editionGuess: res.attributes?.edition_guess ?? null,
        conditionGuess: res.attributes?.condition_guess ?? null,
        rarityScore: res.attributes?.rarity_score ?? null,
      },
      prediction: {
        name: res.prediction?.name ?? '',
        estimatedLow: res.prediction?.estimated_low ?? 0,
        estimatedMid: res.prediction?.estimated_mid ?? 0,
        estimatedHigh: res.prediction?.estimated_high ?? 0,
        currency: res.prediction?.currency ?? 'EUR',
        confidence: res.prediction?.confidence ?? 0,
      },
    };
  }

  async searchItems(query: string): Promise<Item[]> {
    if (!query.trim()) return [];

    const { data, error } = await supabase
      .from('items')
      .select('id,title,image_url,category,value,updated_at')
      .ilike('title', `%${query}%`)
      .order('updated_at', { ascending: false })
      .limit(25);

    if (error) {
      console.warn('[SupabaseDataProvider] searchItems error:', error);
      return [];
    }

    const rows = (data ?? []) as {
      id: string;
      title: string;
      image_url?: string | null;
      category?: string | null;
      value?: number | null;
      updated_at?: string | null;
    }[];

    return rows.map((r) => ({
      id: r.id,
      name: r.title,
      category: r.category || 'Uncategorized',
      price: typeof r.value === 'number' ? r.value : 0,
      imageUrl: r.image_url ?? undefined,
      updatedAt: r.updated_at ?? undefined,
    }));
  }

  async getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
    if (!userId) return null;

    // Query user_public_profile_v1 view (RLS: public SELECT)
    const { data, error } = await supabase
      .from('user_public_profile_v1')
      .select('*')
      .eq('id', userId)
      .single();

    if (error) {
      // Try alternate column name for user ID
      if (error.code === 'PGRST116') {
        // No rows returned
        return null;
      }
      console.warn('[SupabaseDataProvider] getPublicUserProfile error:', error);
      return null;
    }

    if (!data) return null;

    // Log discovered columns for debugging (remove in production)
    console.log('[SupabaseDataProvider] user_public_profile_v1 columns:', Object.keys(data));

    // Map columns flexibly - handle various naming conventions
    const row = data as Record<string, any>;

    return {
      id: row.id ?? row.user_id ?? userId,
      displayName: row.display_name ?? row.displayName ?? row.username ?? row.name ?? 'Unknown',
      handle: row.handle ?? row.username ?? null,
      avatarUrl: row.avatar_url ?? row.avatarUrl ?? null,
      bio: row.bio ?? row.about ?? row.description ?? null,
      interests: row.interests ?? null,
      collectionCount: row.collection_count ?? row.total_items ?? row.item_count ?? null,
      collectionValueEur: row.collection_value_eur ?? row.total_value_eur ?? row.portfolio_value ?? null,
    };
  }

  async getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
    const category = getCategoryById(categoryId);
    if (!category) return null;

    // Fetch items matching category from Supabase
    const items = await this.searchItems(category.name.split(' ')[0]);

    // Filter events by categoryId (from static data for now)
    const upcomingEvents = EVENTS
      .filter((e) => e.categoryId === categoryId)
      .map((e) => ({
        id: e.id,
        title: e.title,
        kind: e.kind,
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
  // DM / Inbox methods
  // ─────────────────────────────────────────────────────────────────────────────

  async listInboxThreads(): Promise<DmThread[]> {
    const { data, error } = await supabase
      .from('v_chat_inbox_v1')
      .select('*')
      .order('last_message_at', { ascending: false });

    if (error) {
      console.warn('[SupabaseDataProvider] listInboxThreads error:', error);
      return [];
    }

    if (!data) return [];

    // Map flexibly to handle various column naming conventions
    return (data as Record<string, any>[]).map((row) => ({
      id: row.id ?? row.thread_id,
      otherUserId: row.other_user_id ?? row.otherUserId,
      otherUserName: row.other_user_name ?? row.otherUserName ?? 'Unknown',
      otherUserHandle: row.other_user_handle ?? row.otherUserHandle ?? null,
      otherUserAvatarUrl: row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null,
      otherUserAvatarColor: row.other_user_avatar_color ?? '#6b7280',
      status: (row.status ?? 'accepted') as DmThreadStatus,
      lastMessagePreview: row.last_message_preview ?? row.lastMessagePreview ?? null,
      lastMessageAt: row.last_message_at ?? row.lastMessageAt ?? null,
      unreadCount: row.unread_count ?? row.unreadCount ?? 0,
      isIncoming: row.is_incoming ?? row.isIncoming ?? false,
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
      console.warn('[SupabaseDataProvider] listIncomingRequests error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, any>[]).map((row) => ({
      threadId: row.id ?? row.thread_id,
      fromUserId: row.other_user_id ?? row.otherUserId,
      fromUserName: row.other_user_name ?? row.otherUserName ?? 'Unknown',
      fromUserHandle: row.other_user_handle ?? row.otherUserHandle ?? null,
      fromUserAvatarUrl: row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null,
      fromUserAvatarColor: row.other_user_avatar_color ?? '#6b7280',
      requestMessage: row.last_message_preview ?? row.lastMessagePreview ?? null,
      requestedAt: row.last_message_at ?? row.lastMessageAt ?? new Date().toISOString(),
    }));
  }

  async requestDm(toUserId: string, message?: string): Promise<string> {
    const { data, error } = await supabase.rpc('rpc_request_dm_v1', {
      p_to_user_id: toUserId,
      p_message: message ?? null,
    });

    if (error) {
      console.error('[SupabaseDataProvider] requestDm error:', error);
      throw new Error(error.message || 'Failed to send DM request');
    }

    // RPC returns the thread ID
    return (data as any)?.thread_id ?? data ?? '';
  }

  async decideDmRequest(threadId: string, accept: boolean): Promise<void> {
    const { error } = await supabase.rpc('rpc_decide_dm_request_v1', {
      p_thread_id: threadId,
      p_accept: accept,
    });

    if (error) {
      console.error('[SupabaseDataProvider] decideDmRequest error:', error);
      throw new Error(error.message || 'Failed to process DM request');
    }
  }

  async markThreadRead(threadId: string): Promise<void> {
    const { error } = await supabase.rpc('rpc_mark_thread_read_v1', {
      p_thread_id: threadId,
    });

    if (error) {
      console.warn('[SupabaseDataProvider] markThreadRead error:', error);
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
      console.warn('[SupabaseDataProvider] getThreadMessages error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, any>[]).map((row) => ({
      id: row.id,
      threadId: row.thread_id ?? threadId,
      authorUserId: row.author_user_id ?? row.authorUserId,
      text: row.text ?? '',
      createdAt: row.created_at ?? row.createdAt ?? new Date().toISOString(),
    }));
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
        twitchCreatorsLive = data.filter((row: any) => row.is_live === true).length;
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
}

// Singleton instance
export const supabaseDataProvider = new SupabaseDataProvider();
