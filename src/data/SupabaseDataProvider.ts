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
} from './types';
import { supabase } from '../lib/supabase';

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
}

// Singleton instance
export const supabaseDataProvider = new SupabaseDataProvider();
