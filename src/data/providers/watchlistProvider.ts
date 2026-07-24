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
        .select('id,title,priority,owned,target_price,currency,category,notes,created_at'),
      SUPABASE_READ_TIMEOUT_MS,
      'listWatchlist',
    );
    data = res.data;
    error = res.error;
  } catch (e) {
    if (e instanceof TimeoutError) {
      logger.warn('[SupabaseDataProvider] listWatchlist timed out — returning empty list');
      return [];
    }
    throw e;
  }

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
    sortOrder: 0, // sort_order column doesn't exist on watchlist_items; UI sorts by priority
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
      currency: 'EUR',
      target_price: input.targetPrice ?? null,
      priority: input.priority ?? 'medium',
      notes: input.notes ?? null,
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
  } catch {
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

export async function updateWatchlistItem(id: string, updates: { targetPrice?: number | null; notes?: string; sortOrder?: number }): Promise<WatchlistItem> {
  const updatePayload: Record<string, unknown> = {};
  if (updates.targetPrice !== undefined) updatePayload.target_price = updates.targetPrice;
  if (updates.notes !== undefined) updatePayload.notes = updates.notes;
  // sort_order isn't a column on watchlist_items — accept the param for
  // API compatibility but ignore it. (Older builds shipped this; the
  // table never gained the column.)

  // Real table is `watchlist_items` (the legacy `watchlist` table has a
  // different shape and was returning 400 on every call).
  const { data, error } = await supabase
    .from('watchlist_items')
    .update(updatePayload)
    .eq('id', id)
    .select('id, title, priority, owned, target_price, currency, category, notes, created_at')
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

  let created: Record<string, unknown>;
  try {
    created = await collectorsApi.post<Record<string, unknown>>('/items', {
      name: row.title,
      category: row.category ?? 'uncategorized',
      purchase_price: actualPrice ?? null,
      // "I Got It!" means the acquisition happened now. Stamping it gives the
      // analytics cost-basis series a real date to bucket on instead of
      // falling back to created_at. NOTE: purchase_currency is not sent — this
      // provider is outside React so it has no settings accessor, and the raw
      // amount is already denominated in whatever the user typed.
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
    logger.warn('[SupabaseDataProvider] convertWatchlistToItem delete failed (item created OK):', e);
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
