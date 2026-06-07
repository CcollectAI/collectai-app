/**
 * Category domain provider — category store, summaries, missing items,
 * ownership, following, and deep-dive analytics.
 */

import type {
  Item,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
} from '../types';
import { getCategoryById } from '../categories';
import { supabase } from '../../lib/supabase';
import { collectorsApi } from '../../api/collectorsApi';
import { withTimeout, TimeoutError } from '../../lib/withTimeout';
import logger from '../../utils/logger';

const SUPABASE_READ_TIMEOUT_MS = 5_000;

export async function getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
  const category = getCategoryById(categoryId);
  if (!category) return null;

  // items columns are `name`, `title`, `image_url` (not `images`). The
  // earlier query referenced a nonexistent `images` array, which made
  // PostgREST 400 with column-not-found and the catch silently returned
  // [] — categories opened to an empty store every time.
  type CatItemRow = { id: string; name?: string | null; title?: string | null; category?: string | null; updated_at?: string | null; image_url?: string | null };
  type EventRow = { id: string; title: string; kind: string; date: string; time?: string };

  // The two queries are independent — fire them in parallel so cellular
  // round-trip latency stacks once, not twice. Each keeps its own timeout
  // and treats a TimeoutError as "return null" (the same semantics as the
  // previous sequential version). Non-timeout errors still propagate.
  const itemsP = (async (): Promise<CatItemRow[] | null> => {
    try {
      const res = await withTimeout(
        supabase
          .from('items')
          .select('id, name, title, category, updated_at, image_url')
          .eq('category', categoryId)
          .order('updated_at', { ascending: false })
          .limit(20),
        SUPABASE_READ_TIMEOUT_MS,
        'getCategoryStore.items',
      );
      return res.data as CatItemRow[] | null;
    } catch (e) {
      if (e instanceof TimeoutError) {
        logger.warn('[SupabaseDataProvider] getCategoryStore.items timed out');
        return null;
      }
      throw e;
    }
  })();

  // Two pools, merged category-first: events tagged to THIS category lead,
  // then the general upcoming pool (what the events tab shows) fills the
  // rest. Without the second pool, categories with no tagged events showed
  // "No upcoming events" while the events tab was full.
  const today = new Date().toISOString().split('T')[0];
  const eventsP = (async (): Promise<EventRow[] | null> => {
    try {
      const [catRes, allRes] = await Promise.all([
        withTimeout(
          supabase
            .from('v_events_with_attendees_v1')
            .select('id, title, kind, date, time')
            .eq('category_id', categoryId)
            .gte('date', today)
            .order('date', { ascending: true })
            .limit(5),
          SUPABASE_READ_TIMEOUT_MS,
          'getCategoryStore.events',
        ),
        withTimeout(
          supabase
            .from('v_events_with_attendees_v1')
            .select('id, title, kind, date, time')
            .gte('date', today)
            .order('date', { ascending: true })
            .limit(5),
          SUPABASE_READ_TIMEOUT_MS,
          'getCategoryStore.eventsAll',
        ),
      ]);
      const catEvents = (catRes.data ?? []) as EventRow[];
      const allEvents = (allRes.data ?? []) as EventRow[];
      const seen = new Set(catEvents.map((e) => e.id));
      return [...catEvents, ...allEvents.filter((e) => !seen.has(e.id))].slice(0, 5);
    } catch (e) {
      if (e instanceof TimeoutError) {
        logger.warn('[SupabaseDataProvider] getCategoryStore.events timed out');
        return null;
      }
      throw e;
    }
  })();

  const [itemsData, eventsData] = await Promise.all([itemsP, eventsP]);

  const items: Item[] = (itemsData ?? []).map((r) => ({
    id: r.id,
    name: r.name ?? r.title ?? 'Untitled',
    category: r.category ?? categoryId,
    price: 0,
    imageUrl: r.image_url ?? undefined,
    updatedAt: r.updated_at ?? new Date().toISOString(),
  }));

  const upcomingEvents = (eventsData ?? []).map((e) => ({
    id: e.id,
    title: e.title,
    kind: e.kind as 'collection_drop' | 'meetup' | 'stream',
    date: e.date,
    time: e.time,
  }));

  // R50k: catalog reference images moved backend-only; no spotlight slides
  // fed from category_items.image_url in the mobile app anymore.
  const spotlightSlides: import('@/data/types').SpotlightSlide[] = [];

  return {
    categoryId: category.id,
    categoryName: category.name,
    categoryTagline: category.tagline,
    bannerImageUrl: category.bannerImageUrl,
    spotlightSlides,
    items,
    upcomingEvents,
    friendsWhoFollow: [],
  };
}

export async function listCategorySummaries(): Promise<CategorySummary[]> {
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

export async function listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
  type MissingRow = { id: string; category_id: string; title: string; brand?: string; notes?: string };
  let data: MissingRow[] | null = null;
  let error: unknown = null;
  try {
    // Cap the payload: this view returns the ENTIRE missing-items set for the
    // category (e.g. ~3,400 rows for lego, ~900ms + a multi-MB JSON transfer on
    // cellular) and it blocks the category-screen skeleton. The checklist UI
    // only surfaces a handful, so 150 is plenty and keeps the page snappy.
    const res = await withTimeout(
      supabase
        .from('v_category_missing_items_v1')
        .select('id, category_id, title, brand, notes')
        .eq('category_id', categoryId)
        .limit(150),
      SUPABASE_READ_TIMEOUT_MS,
      'listCategoryMissing',
    );
    data = res.data as MissingRow[] | null;
    error = res.error;
  } catch (e) {
    if (e instanceof TimeoutError) {
      logger.warn('[SupabaseDataProvider] listCategoryMissing timed out');
      return [];
    }
    throw e;
  }

  if (error) {
    logger.warn('[SupabaseDataProvider] listCategoryMissing error:', error);
    return [];
  }

  return (data ?? []).map((row) => ({
    id: row.id,
    categoryId: row.category_id,
    title: row.title,
    brand: row.brand,
    notes: row.notes,
  }));
}

export async function markCategoryItemOwned(
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

// Category follow/unfollow lives on the EC2 backend at
// /events/categories/{id}/follow (POST/DELETE) and
// /events/categories/followed (GET) and
// /events/categories/{id}/following (GET). The earlier Supabase RPC
// path (rpc_follow_category_v1 etc.) was never deployed; calls 404'd
// silently because errors are caught and the provider returned
// false / [] / void. Fix: route through collectorsApi.

export async function followCategory(categoryId: string): Promise<void> {
  try {
    await collectorsApi.post(`/events/categories/${encodeURIComponent(categoryId)}/follow`, {});
  } catch (e) {
    logger.error('[SupabaseDataProvider] followCategory error:', e);
    throw e instanceof Error ? e : new Error('Failed to follow category');
  }
}

export async function unfollowCategory(categoryId: string): Promise<void> {
  try {
    await collectorsApi.delete(`/events/categories/${encodeURIComponent(categoryId)}/follow`);
  } catch (e) {
    logger.error('[SupabaseDataProvider] unfollowCategory error:', e);
    throw e instanceof Error ? e : new Error('Failed to unfollow category');
  }
}

export async function listFollowedCategories(): Promise<string[]> {
  try {
    // Server returns `{categories: string[]}` (events_core.py:500). The
    // earlier `{category_id: string}[]` shape was wishful thinking — the
    // map(r.category_id) produced [undefined,...] whenever the user had
    // any follows.
    const data = await collectorsApi.get<{ categories?: string[] }>(
      '/events/categories/followed',
    );
    return data?.categories ?? [];
  } catch (e) {
    logger.warn('[SupabaseDataProvider] listFollowedCategories error:', e);
    return [];
  }
}

export async function isFollowingCategory(categoryId: string): Promise<boolean> {
  try {
    const data = await collectorsApi.get<{ following?: boolean }>(
      `/events/categories/${encodeURIComponent(categoryId)}/following`,
    );
    return Boolean(data?.following);
  } catch (e) {
    logger.warn('[SupabaseDataProvider] isFollowingCategory error:', e);
    return false;
  }
}

export async function getCategoryDeepDive(categoryId: string, days?: number): Promise<Record<string, unknown>> {
  const params = days ? `?days=${days}` : '';
  return await collectorsApi.get(`/analytics/categories/${categoryId}/deep-dive${params}`) as Record<string, unknown>;
}
