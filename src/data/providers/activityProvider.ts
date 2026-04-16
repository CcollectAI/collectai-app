/**
 * Activity domain provider — activity feed, logging, unified search.
 */

import type { ActivityFeedItem, ActivityType } from '../types';
import {
  getUserActivity as apiGetUserActivity,
  logActivity as apiLogActivity,
  unifiedSearch as apiUnifiedSearch,
} from '../../api/collectorsApi';
import logger from '../../utils/logger';

export async function getUserActivity(userId: string, limit = 20, offset = 0): Promise<ActivityFeedItem[]> {
  try {
    const resp = await apiGetUserActivity(userId, limit, offset) as Record<string, unknown>;
    return ((resp.activities as Record<string, unknown>[]) || []).map((a) => ({
      id: a.id as string,
      userId: a.user_id as string,
      activityType: a.activity_type as ActivityType,
      title: a.title as string,
      description: (a.description as string | null) ?? null,
      metadata: (a.metadata as Record<string, unknown>) || {},
      isPublic: a.is_public as boolean,
      createdAt: a.created_at as string,
    }));
  } catch {
    return [];
  }
}

export async function logActivity(activityType: string, title: string, description?: string, metadata?: Record<string, unknown>, isPublic = true): Promise<void> {
  try {
    await apiLogActivity({
      activity_type: activityType,
      title,
      description,
      metadata: metadata || {},
      is_public: isPublic,
    });
  } catch (err: unknown) {
    logger.warn('[SupabaseDataProvider] logActivity error:', err);
  }
}

export async function unifiedSearch(query: string, limit = 5) {
  try {
    const resp = await apiUnifiedSearch(query, limit) as Record<string, unknown>;
    return {
      items: ((resp.items as Record<string, unknown>[]) || []).map((i) => ({
        id: i.id as string,
        name: i.name as string,
        category: i.category as string,
        imageUrl: (i.image_url ?? i.imageUrl ?? null) as string | null,
        price: i.price as number | undefined,
      })),
      catalog: ((resp.catalog as Record<string, unknown>[]) || []).map((c) => ({
        id: c.id as string,
        category: c.category as string,
        itemKey: (c.item_key ?? c.itemKey) as string,
        title: c.title as string,
        brand: (c.brand ?? null) as string | null,
        // R50k: catalog reference images backend-only
        hasReferenceImage: Boolean(c.has_reference_image ?? false),
      })),
      users: ((resp.users as Record<string, unknown>[]) || []).map((u) => ({
        id: u.id as string,
        displayName: (u.display_name ?? u.displayName) as string,
        handle: u.handle as string | undefined,
        avatarUrl: (u.avatar_url ?? u.avatarUrl ?? null) as string | null,
      })),
      events: ((resp.events as Record<string, unknown>[]) || []).map((e) => ({
        id: e.id as string,
        title: e.title as string,
        startDate: (e.start_date ?? e.startDate) as string | undefined,
        location: e.location as string | undefined,
        category: e.category as string | undefined,
      })),
      categories: (resp.categories as { id: string; name: string }[]) || [],
    };
  } catch {
    return { items: [], catalog: [], users: [], events: [], categories: [] };
  }
}
