/**
 * Category domain provider — category store, summaries, missing items,
 * ownership, following, and deep-dive analytics.
 */

import type {
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
  type EventRow = { id: string; title: string; kind: string; date: string; time?: string };

  // The two queries are independent — fire them in parallel so cellular
  // round-trip latency stacks once, not twice. Each keeps its own timeout
  // and treats a TimeoutError as "return null" (the same semantics as the
  // previous sequential version). Non-timeout errors still propagate.
  // ── The items query lived HERE and is gone (2026-08-19) ──────────────
  // It selected your items in this category on EVERY category open, and
  // nothing had rendered them since the 2026-08-11 museum redesign removed
  // "Items-in-Category" — a round trip per open, for a value nobody read.
  //
  // Its mapper also hardcoded `price: 0`, so anyone who wired it back up
  // would have priced the whole shelf at zero (unknown-as-zero, the house bug
  // class). The category page's "YOUR COLLECTION" rail deliberately does NOT
  // use this: it reads `dataProvider.listItems({ category })`, which goes
  // through the single `mapItemRow` call site and therefore shows the same
  // number as the Items tab and the portfolio total.

  // Strict category-relevant: ONLY events tagged to THIS category. Categories
  // with none show "No upcoming events" rather than filling the section with
  // off-topic events from a general pool (user decision 2026-06-18). Events
  // genuinely exist for ~10/54 categories (taylor_swift, kpop_merch, lego…).
  const today = new Date().toISOString().split('T')[0];
  const eventsP = (async (): Promise<EventRow[] | null> => {
    try {
      const catRes = await withTimeout(
        supabase
          .from('v_events_with_attendees_v1')
          .select('id, title, kind, date, time')
          .eq('category_id', categoryId)
          .gte('date', today)
          .order('date', { ascending: true })
          .limit(5),
        SUPABASE_READ_TIMEOUT_MS,
        'getCategoryStore.events',
      );
      return (catRes.data ?? []) as EventRow[];
    } catch (e) {
      if (e instanceof TimeoutError) {
        logger.error('[SupabaseDataProvider] getCategoryStore.events timed out');
        return null;
      }
      throw e;
    }
  })();

  const eventsData = await eventsP;


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
    upcomingEvents,
    friendsWhoFollow: [],
  };
}

export async function listCategorySummaries(): Promise<CategorySummary[]> {
  const { data, error } = await supabase
    .from('v_category_summaries_v1')
    .select('id, name, completion_pct, owned_count, missing_count, total_count');

  if (error) {
    // THROW, not `return []`. An empty array is indistinguishable from "you
    // have none", so a failed read renders as an empty feature — the house bug
    // class (CLAUDE.md). logger.ERROR because warn is stripped in release.
    logger.error('[SupabaseDataProvider] listCategorySummaries error:', error);
    throw new Error(
      typeof (error as { message?: string })?.message === 'string'
        ? (error as { message: string }).message
        : 'Could not load CategorySummaries',
    );
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
      logger.error('[SupabaseDataProvider] listCategoryMissing timed out');
      return [];
    }
    throw e;
  }

  if (error) {
    // THROW, not `return []`. An empty array is indistinguishable from "you
    // have none", so a failed read renders as an empty feature — the house bug
    // class (CLAUDE.md). logger.ERROR because warn is stripped in release.
    logger.error('[SupabaseDataProvider] listCategoryMissing error:', error);
    throw new Error(
      typeof (error as { message?: string })?.message === 'string'
        ? (error as { message: string }).message
        : 'Could not load CategoryMissing',
    );
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
    logger.error('[SupabaseDataProvider] listFollowedCategories error:', e);
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
    logger.error('[SupabaseDataProvider] isFollowingCategory error:', e);
    return false;
  }
}

// Delegates to collectorsApi.getCategoryDeepDive (src/api/miscApi.ts) instead
// of building the request here. The hand-rolled version inherited httpClient's
// 5s default, but a cold deep-dive runs a 1M+ row aggregation — so the card
// timed out, the screen swallowed the rejection into logger.info (stripped in
// TestFlight), and the section rendered nothing. Keeping one implementation
// means the 20s timeout and the URL encoding can't drift apart again.
export async function getCategoryDeepDive(categoryId: string, days?: number): Promise<Record<string, unknown>> {
  return await collectorsApi.getCategoryDeepDive(categoryId, days) as Record<string, unknown>;
}
