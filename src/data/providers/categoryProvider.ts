/**
 * Category domain provider — category store, summaries, missing items,
 * ownership, following, and deep-dive analytics.
 */

import { API_LIMITS } from '@/constants/apiLimits';
import type {
  Item,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
} from '../types';
import { getCategoryById } from '../categories';
import { supabase } from '../../lib/supabase';
import { collectorsApi } from '../../api/collectorsApi';
import logger from '../../utils/logger';

export async function getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
  const category = getCategoryById(categoryId);
  if (!category) return null;

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

  // Fetch spotlight items from catalog (category_items with images, highest value first)
  const { data: spotlightData } = await supabase
    .from('category_items')
    .select('item_key, title, image_url, attributes_json')
    .eq('category', categoryId)
    .not('image_url', 'is', null)
    .order('item_key', { ascending: true })
    .limit(8);

  type SpotlightRow = { item_key: string; title: string; image_url?: string | null; attributes_json?: Record<string, unknown> | null };
  const spotlightSlides = (spotlightData ?? [])
    .filter((r: SpotlightRow) => r.image_url)
    .map((r: SpotlightRow) => ({
      id: r.item_key,
      title: r.title ?? 'Unknown',
      subtitle: (r.attributes_json as Record<string, string> | null)?.brand
        ?? (r.attributes_json as Record<string, string> | null)?.set_name
        ?? undefined,
      imageUrl: r.image_url ?? undefined,
    }));

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

export async function followCategory(categoryId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_follow_category_v1', {
    p_category_id: categoryId,
  });
  if (error) {
    logger.error('[SupabaseDataProvider] followCategory error:', error);
    throw new Error(error.message || 'Failed to follow category');
  }
}

export async function unfollowCategory(categoryId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_unfollow_category_v1', {
    p_category_id: categoryId,
  });
  if (error) {
    logger.error('[SupabaseDataProvider] unfollowCategory error:', error);
    throw new Error(error.message || 'Failed to unfollow category');
  }
}

export async function listFollowedCategories(): Promise<string[]> {
  const { data, error } = await supabase.rpc('rpc_list_followed_categories_v1');
  if (error) {
    logger.warn('[SupabaseDataProvider] listFollowedCategories error:', error);
    return [];
  }
  return (data ?? []).map((row: { category_id: string }) => row.category_id);
}

export async function isFollowingCategory(categoryId: string): Promise<boolean> {
  const { data, error } = await supabase.rpc('rpc_is_following_category_v1', {
    p_category_id: categoryId,
  });
  if (error) {
    logger.warn('[SupabaseDataProvider] isFollowingCategory error:', error);
    return false;
  }
  return data === true;
}

export async function getCategoryDeepDive(categoryId: string, days?: number): Promise<Record<string, unknown>> {
  const params = days ? `?days=${days}` : '';
  return await collectorsApi.get(`/analytics/categories/${categoryId}/deep-dive${params}`) as Record<string, unknown>;
}
