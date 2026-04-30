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
import logger from '../../utils/logger';

export async function listWatchlist(_userId: string): Promise<WatchlistItem[]> {
  const { data, error } = await supabase
    .from('v_watchlist_items_v1')
    .select('id,title,priority,owned,target_price,currency,category,notes,created_at,sort_order');

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
    sortOrder: r.sort_order ?? 0,
  }));
}

export async function addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
  // Lives on EC2 at POST /watchlist/mine. The Supabase RPC
  // rpc_add_watchlist_item_v1 was never deployed; calls used to throw
  // "Could not find the function" silently.
  let r: Record<string, unknown>;
  try {
    // Server contract (WatchlistCreate): name, category, item_id?,
    // predicted_value?, currency?. Sending `title` was wrong; the
    // server reads `name` and stores it as watchlist_items.title.
    // E2E-verified against POST /watchlist/mine 2026-04-30.
    const data = await collectorsApi.post<Record<string, unknown>>('/watchlist/mine', {
      name: input.title,
      category: input.category,
      currency: 'EUR',
    });
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
    title: typeof r.title === 'string' ? r.title : String(r.title ?? ''),
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
