/**
 * Watchlist domain provider — watchlist CRUD + conversion to portfolio item.
 */

import type {
  CurrencyCode,
  WatchlistItem,
  CreateWatchlistInput,
  Item,
} from '../types';
import { supabase } from '../../lib/supabase';
import { collectorsApi } from '../../api/collectorsApi';
import { withTimeout, TimeoutError } from '../../lib/withTimeout';
import logger from '../../utils/logger';
import { getSettingsSnapshot } from '../../lib/settings';

const SUPABASE_READ_TIMEOUT_MS = 5_000;

export async function listWatchlist(_userId: string): Promise<WatchlistItem[]> {
  // The view `v_watchlist_items_v1` was never deployed (despite the
  // `_v1` naming convention used elsewhere). The data lives directly in
  // `watchlist_items`, which RLS scopes to the current user. Bare-table
  // read is fine. Also drop `sort_order` — the column doesn't exist on
  // the table; downstream code falls back to `priority`-based ordering.
  // Found by audit_full_chain.py 2026-05-01.
  let data: unknown;
  let error: unknown;
  try {
    const res = await withTimeout(
      supabase
        .from('watchlist_items')
        .select('id,title,priority,owned,target_price,currency,category,notes,created_at,sort_order'),
      SUPABASE_READ_TIMEOUT_MS,
      'listWatchlist',
    );
    data = res.data;
    error = res.error;
  } catch (e) {
    if (e instanceof TimeoutError) {
      // THROW, do not return []. An empty array here is indistinguishable from
      // "you have not saved anything", so a failed read rendered as
      // "No items in your watchlist yet" — telling a user their watchlist is
      // empty when we simply could not fetch it.
      //
      // That matters more here than on most screens: the watchlist IS the paid
      // feature's input (`_check_watchlist_snipes` reads target_price), so a
      // user who believes it emptied has no reason to keep paying.
      //
      // Safe to throw: CachedDataProvider.swr only awaits the fetcher when
      // there is NO cached value, and keeps serving stale data otherwise — so
      // this surfaces on a cold read and degrades to stale-plus-log on a warm
      // one, which is the correct stale-while-revalidate behaviour.
      logger.error('[SupabaseDataProvider] listWatchlist timed out');
      throw e;
    }
    throw e;
  }

  if (error) {
    // logger.ERROR, not warn — warn is stripped in release builds, so this was
    // invisible on exactly the builds where a vanished watchlist matters.
    logger.error('[SupabaseDataProvider] listWatchlist error:', error);
    throw new Error(
      typeof (error as { message?: string })?.message === 'string'
        ? (error as { message: string }).message
        : 'Could not load your watchlist',
    );
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
    sort_order?: number | null;
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
    // Real column since 2026-07-31. NULL means the user has never reordered, so
    // 0 keeps them in the pre-existing priority-based ordering.
    sortOrder: typeof r.sort_order === 'number' ? r.sort_order : 0,
  }));
}

export async function addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
  // Lives on EC2 at POST /watchlist/mine. The Supabase RPC
  // rpc_add_watchlist_item_v1 was never deployed; calls used to throw
  // "Could not find the function" silently.
  let r: Record<string, unknown>;
  try {
    // Server contract (WatchlistCreate): name, category, target_price?,
    // priority?, notes?, item_id?, predicted_value?, currency?. Sending
    // `title` was wrong; the server reads `name` and stores it as
    // watchlist_items.title. E2E-verified 2026-04-30. target_price /
    // priority / notes were silently DROPPED here until 2026-06-05 —
    // every add-screen (wishlist tab, watchlist-builder, catalog museum)
    // was sending them into the void while the columns sat in the table.
    // 15s timeout (vs the 5s httpClient default): the write commits fast now
    // that demand-signal recording is fire-and-forget server-side, but a 5s
    // cap left no headroom under pooler pressure and surfaced spurious
    // "Couldn't add to watchlist" errors on a write that actually succeeded.
    const data = await collectorsApi.post<Record<string, unknown>>('/watchlist/mine', {
      name: input.title,
      category: input.category,
      // NOT hardcoded 'EUR'. The target is whatever number the caller watched
      // — usually a listing's asking price, which can be in any of the 7
      // currencies a seller may price in — and the alert converts using this
      // column. Stamping every row EUR made the conversion a no-op.
      currency: (input.targetPriceCurrency || 'EUR').toUpperCase(),
      target_price: input.targetPrice ?? null,
      priority: input.priority ?? 'medium',
      notes: input.notes ?? null,
      // WatchlistCreate.item_id has always existed server-side; nothing ever
      // sent it, so watchlist_items.item_id was NULL on every row.
      item_id: input.itemId ?? null,
    }, { timeoutMs: 15_000 });
    r = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
  } catch (e) {
    logger.error('[SupabaseDataProvider] addWatchlistItem error:', e);
    throw e instanceof Error ? e : new Error('Failed to add watchlist item');
  }
  if (!r || !r.id) {
    throw new Error('No data returned from /watchlist/mine');
  }

  // Push-engagement loop: attribute outcome if a recent push tap led
  // here (e.g. drop alert → "follow this item"). No-ops when no tap.
  try {
    const { emitOutcome } = await import('@/lib/notificationOutcomeTracker');
    emitOutcome('followed', { watchlist_id: r.id, title: input.title });
  } catch (e) {
    logger.error('[silent-catch] watchlistProvider.ts:118:', e);
    // best-effort
  }

  return {
    id: typeof r.id === 'string' ? r.id : String(r.id ?? ''),
    // The server's response field is `name` (it aliases watchlist_items.title
    // on the way out) — reading `r.title` returned '' for every fresh add,
    // which blanked optimistic rows in watchlist-builder until a refetch.
    title: typeof r.name === 'string' ? r.name : (typeof r.title === 'string' ? r.title : ''),
    priority: (['high', 'medium', 'low'].includes(r.priority as string) ? r.priority as 'high' | 'medium' | 'low' : 'medium'),
    owned: typeof r.owned === 'boolean' ? r.owned : false,
    targetPrice: typeof r.target_price === 'number' ? r.target_price : null,
    currency: (typeof r.currency === 'string' && r.currency ? r.currency as CurrencyCode : 'EUR'),
    category: typeof r.category === 'string' ? r.category : undefined,
    notes: typeof r.notes === 'string' ? r.notes : undefined,
    createdAt: typeof r.created_at === 'string' ? r.created_at : undefined,
  };
}

export async function updateWatchlistItem(id: string, updates: { targetPrice?: number | null; targetPriceCurrency?: string | null; notes?: string; sortOrder?: number }): Promise<WatchlistItem> {
  const updatePayload: Record<string, unknown> = {};
  if (updates.targetPrice !== undefined) updatePayload.target_price = updates.targetPrice;
  // Currency travels WITH the number, and only with it. A member who set a
  // target in EUR and later switched their display currency to JPY types the
  // new target in JPY — writing the number without re-stamping the currency
  // would relabel it EUR and hand Target Hit a figure ~164x off. Writing the
  // currency ALONE is worse still: it silently reinterprets a number the
  // member never touched.
  if (updates.targetPrice !== undefined && updates.targetPriceCurrency) {
    updatePayload.currency = updates.targetPriceCurrency.toUpperCase();
  }
  if (updates.notes !== undefined) updatePayload.notes = updates.notes;
  // `sort_order` was dropped here because the column did not exist, which made
  // watchlist-builder's move up/down buttons fail EVERY time: the payload came
  // out empty, `.update({})` matched 0 rows, and the chained `.single()` threw
  // PGRST116 ("The result contains 0 rows", HTTP 406) — so the screen rolled
  // back the optimistic reorder and showed "Could not reorder. Please try
  // again." Column added 2026-07-31
  // (20260731_watchlist_items_sort_order.sql).
  if (updates.sortOrder !== undefined) updatePayload.sort_order = updates.sortOrder;

  // Nothing to write — return the row unchanged rather than issuing an empty
  // update, which PostgREST answers with 0 rows and `.single()` turns into a
  // throw. This is the guard that would have made the bug above impossible.
  if (Object.keys(updatePayload).length === 0) {
    const { data: current, error: readErr } = await supabase
      .from('watchlist_items')
      .select('id, title, priority, owned, target_price, currency, category, notes, created_at, sort_order')
      .eq('id', id)
      .single();
    if (readErr) {
      logger.error('[SupabaseDataProvider] updateWatchlistItem no-op read error:', readErr);
      throw new Error(readErr.message || 'Failed to load watchlist item');
    }
    const c = current as Record<string, unknown>;
    return {
      id: typeof c.id === 'string' ? c.id : String(c.id ?? ''),
      title: typeof c.title === 'string' ? c.title : '',
      priority: (['high', 'medium', 'low'].includes(c.priority as string) ? c.priority as 'high' | 'medium' | 'low' : 'medium'),
      owned: typeof c.owned === 'boolean' ? c.owned : false,
      targetPrice: typeof c.target_price === 'number' ? c.target_price : null,
      currency: (typeof c.currency === 'string' && c.currency ? c.currency as CurrencyCode : 'EUR'),
      category: typeof c.category === 'string' ? c.category : undefined,
      notes: typeof c.notes === 'string' ? c.notes : undefined,
      createdAt: typeof c.created_at === 'string' ? c.created_at : undefined,
      sortOrder: typeof c.sort_order === 'number' ? c.sort_order : 0,
    };
  }

  // Real table is `watchlist_items` (the legacy `watchlist` table has a
  // different shape and was returning 400 on every call).
  const { data, error } = await supabase
    .from('watchlist_items')
    .update(updatePayload)
    .eq('id', id)
    .select('id, title, priority, owned, target_price, currency, category, notes, created_at, sort_order')
    .single();

  if (error) {
    logger.error('[SupabaseDataProvider] updateWatchlistItem error:', error);
    throw new Error(error.message || 'Failed to update watchlist item');
  }

  const r = data as Record<string, unknown>;
  return {
    id: typeof r.id === 'string' ? r.id : String(r.id ?? ''),
    title: typeof r.title === 'string' ? r.title : String(r.title ?? ''),
    priority: (['high', 'medium', 'low'].includes(r.priority as string) ? r.priority as 'high' | 'medium' | 'low' : 'medium'),
    owned: typeof r.owned === 'boolean' ? r.owned : false,
    targetPrice: typeof r.target_price === 'number' ? r.target_price : null,
    currency: (typeof r.currency === 'string' && r.currency ? r.currency as CurrencyCode : 'EUR'),
    category: typeof r.category === 'string' ? r.category : undefined,
    notes: typeof r.notes === 'string' ? r.notes : undefined,
    createdAt: typeof r.created_at === 'string' ? r.created_at : undefined,
    sortOrder: typeof r.sort_order === 'number' ? r.sort_order : 0,
  };
}

export async function removeWatchlistItem(id: string): Promise<void> {
  // Lives on EC2 at DELETE /watchlist/mine/{watch_id}.
  try {
    await collectorsApi.delete(`/watchlist/mine/${encodeURIComponent(id)}`);
  } catch (e) {
    logger.error('[SupabaseDataProvider] removeWatchlistItem error:', e);
    throw e instanceof Error ? e : new Error('Failed to remove watchlist item');
  }
}

export async function removeWatchlistItems(ids: string[]): Promise<void> {
  const errors: string[] = [];
  for (const id of ids) {
    try {
      await removeWatchlistItem(id);
    } catch (err) {
      logger.error('[silent-catch] watchlistProvider.ts:190:', err);
      errors.push(err instanceof Error ? err.message : String(err));
    }
  }
  if (errors.length > 0) {
    throw new Error(`Failed to remove ${errors.length} item(s): ${errors[0]}`);
  }
}

export async function convertWatchlistToItem(
  watchlistItemId: string,
  actualPrice?: number,
  notes?: string,
): Promise<Item> {
  // rpc_convert_watchlist_to_item_v1 was never deployed — every "Acquire"
  // tap from the wishlist threw "Could not find the function". Compose
  // the conversion at the boundary using the two endpoints that already
  // exist:
  //   1. read title/category from watchlist_items (Supabase RLS-safe;
  //      the v_watchlist_items_v1 view referenced earlier was never deployed)
  //   2. POST /items with actualPrice as purchase_price
  //   3. DELETE /watchlist/mine/{id} to clear the now-acquired row
  // If POST /items fails, leave the watchlist row in place so the user
  // can retry. If DELETE fails after a successful insert, surface a
  // partial-success warning but keep the new item.
  const { data: w, error: wErr } = await supabase
    .from('watchlist_items')
    .select('id, title, category')
    .eq('id', watchlistItemId)
    .maybeSingle();
  if (wErr || !w) {
    logger.error('[SupabaseDataProvider] convertWatchlistToItem read error:', wErr);
    throw new Error(wErr?.message || 'Watchlist item not found');
  }
  const row = w as { id: string; title: string; category?: string | null };

  // `actualPrice` is denominated in whatever currency the user is running the
  // app in, so the server needs to be told which one. Until 2026-07-28 this
  // was omitted — the comment here claimed no settings accessor existed
  // outside React — and the server fell back to EUR, so a USD user who paid
  // $100 had €100 booked as their cost basis. getSettingsSnapshot() reads the
  // same persisted blob SettingsProvider boots from.
  const { currency } = await getSettingsSnapshot();

  let created: Record<string, unknown>;
  try {
    created = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: row.title,
      category: row.category ?? 'uncategorized',
      purchase_price: actualPrice ?? null,
      purchase_currency: currency,
      // "I Got It!" means the acquisition happened now. Stamping it gives the
      // analytics cost-basis series a real date to bucket on instead of
      // falling back to created_at.
      purchased_at: new Date().toISOString(),
      notes: notes ?? null,
    });
  } catch (e) {
    logger.error('[SupabaseDataProvider] convertWatchlistToItem create error:', e);
    throw e instanceof Error ? e : new Error('Failed to create item from watchlist');
  }

  // Best-effort delete; if it fails, the item already exists (more user
  // value preserved than rolling back) and a future tap will hit "Item
  // already in collection" rather than re-converting.
  try {
    await collectorsApi.delete(`/watchlist/mine/${encodeURIComponent(watchlistItemId)}`);
  } catch (e) {
    logger.error('[SupabaseDataProvider] convertWatchlistToItem delete failed (item created OK):', e);
  }

  return {
    id: (created.id as string) ?? `item-${Date.now()}`,
    name: ((created.name ?? created.title ?? row.title) as string | null) ?? 'Untitled',
    category: (created.category as string | null) ?? row.category ?? 'Other',
    price: (created.purchase_price as number | null) ?? actualPrice ?? 0,
    imageUrl: (created.image_url as string | null) ?? undefined,
    updatedAt: (created.updated_at as string | null) ?? new Date().toISOString(),
  };
}
