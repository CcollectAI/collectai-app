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

  const r = (Array.isArray(data) ? data[0] : data) as Record<string, unknown>;
  if (!r) {
    throw new Error('No data returned from RPC');
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
  if (updates.sortOrder !== undefined) updatePayload.sort_order = updates.sortOrder;

  const { data, error } = await supabase
    .from('watchlist')
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
  const { error } = await supabase.rpc('rpc_remove_watchlist_item_v1', {
    p_id: id,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] removeWatchlistItem RPC error:', error);
    throw new Error(error.message || 'Failed to remove watchlist item');
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
