/**
 * watchlistAndAlerts.ts
 *
 * Thin helpers around Supabase for:
 * - Watchlist items (owned or not)
 * - Price alerts
 *
 * These are intentionally simple functions you can call from screens
 * or hooks. No global state here.
 */

import { supabase } from '@/lib/supabase';
import { logger } from '@/lib/logger';

export type WatchlistPriority = 'high' | 'medium' | 'low';

export type WatchlistItem = {
  id: string;
  user_id: string;
  item_id: string | null;
  title: string;
  notes: string | null;
  rank: number | null;
  priority: WatchlistPriority;
  owned: boolean;
  target_price: number | null;
  currency: string;
  created_at: string;
  updated_at: string;
};

export type AlertDirection = 'above' | 'below';

export type AlertRow = {
  id: string;
  user_id: string;
  item_id: string | null;
  watchlist_item_id: string | null;
  direction: AlertDirection;
  threshold: number;
  currency: string;
  active: boolean;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
};

export async function fetchWatchlistForUser(
  userId: string,
): Promise<WatchlistItem[]> {
  if (!userId) return [];

  const { data, error } = await supabase
    .from('watchlist_items')
    .select('*')
    .eq('user_id', userId)
    .order('rank', { ascending: true, nullsFirst: true })
    .order('created_at', { ascending: true });

  if (error) {
    logger.warn('[fetchWatchlistForUser] error', error);
    return [];
  }

  return (data ?? []) as WatchlistItem[];
}

export type UpsertWatchlistPayload = {
  id?: string;
  user_id: string;
  item_id?: string | null;
  title: string;
  notes?: string | null;
  rank?: number | null;
  priority?: WatchlistPriority;
  owned?: boolean;
  target_price?: number | null;
  currency?: string;
};

export async function upsertWatchlistItem(
  payload: UpsertWatchlistPayload,
): Promise<WatchlistItem | null> {
  const body: Record<string, string | number | boolean | null> = {
    user_id: payload.user_id,
    title: payload.title,
    notes: payload.notes ?? null,
    item_id:
      typeof payload.item_id === 'string'
        ? payload.item_id
        : null,
    rank:
      typeof payload.rank === 'number'
        ? payload.rank
        : null,
    priority: payload.priority ?? 'medium',
    owned: payload.owned ?? false,
    target_price:
      typeof payload.target_price === 'number'
        ? payload.target_price
        : null,
    currency: payload.currency ?? 'EUR',
  };

  let query = supabase.from('watchlist_items').upsert(
    payload.id ? { id: payload.id, ...body } : body,
  );

  if (!payload.id) {
    query = query.select('*').single();
  } else {
    query = query.select('*').eq('id', payload.id).single();
  }

  const { data, error } = await query;

  if (error) {
    logger.warn('[upsertWatchlistItem] error', error);
    return null;
  }

  return data as WatchlistItem;
}

export async function deleteWatchlistItem(id: string): Promise<boolean> {
  if (!id) return false;

  const { error } = await supabase
    .from('watchlist_items')
    .delete()
    .eq('id', id);

  if (error) {
    logger.warn('[deleteWatchlistItem] error', error);
    return false;
  }
  return true;
}

export async function fetchAlertsForUser(
  userId: string,
): Promise<AlertRow[]> {
  if (!userId) return [];

  const { data, error } = await supabase
    .from('alerts')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false });

  if (error) {
    logger.warn('[fetchAlertsForUser] error', error);
    return [];
  }

  return (data ?? []) as AlertRow[];
}

export type CreateAlertPayload = {
  user_id: string;
  item_id?: string | null;
  watchlist_item_id?: string | null;
  direction: AlertDirection;
  threshold: number;
  currency?: string;
};

export async function createAlert(
  payload: CreateAlertPayload,
): Promise<AlertRow | null> {
  const body: Record<string, string | number | null> = {
    user_id: payload.user_id,
    direction: payload.direction,
    threshold: payload.threshold,
    currency: payload.currency ?? 'EUR',
    item_id:
      typeof payload.item_id === 'string'
        ? payload.item_id
        : null,
    watchlist_item_id:
      typeof payload.watchlist_item_id === 'string'
        ? payload.watchlist_item_id
        : null,
  };

  const { data, error } = await supabase
    .from('alerts')
    .insert(body)
    .select('*')
    .single();

  if (error) {
    logger.warn('[createAlert] error', error);
    return null;
  }

  return data as AlertRow;
}

export async function toggleAlertActive(
  id: string,
  active: boolean,
): Promise<boolean> {
  if (!id) return false;

  const { error } = await supabase
    .from('alerts')
    .update({ active, updated_at: new Date().toISOString() })
    .eq('id', id);

  if (error) {
    logger.warn('[toggleAlertActive] error', error);
    return false;
  }

  return true;
}
