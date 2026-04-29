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
    const data = await collectorsApi.get<{ categories?: { category_id: string }[] }>(
      '/events/categories/followed',
    );
    const rows = (data?.categories ?? []) as { category_id: string }[];
    return rows.map((r) => r.category_id);
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
