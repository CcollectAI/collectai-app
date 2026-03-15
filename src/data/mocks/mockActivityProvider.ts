/**
 * Mock activity feed domain provider.
 */

import type { ActivityFeedItem } from '../types';

export async function getUserActivity(userId: string, limit = 20, offset = 0): Promise<ActivityFeedItem[]> {
  return [
    { id: '1', userId, activityType: 'item_added' as const, title: 'Added Charizard Base Set', description: null, metadata: {}, isPublic: true, createdAt: new Date().toISOString() },
    { id: '2', userId, activityType: 'event_rsvp' as const, title: "RSVP'd to Pokemon TCG Night", description: null, metadata: {}, isPublic: true, createdAt: new Date(Date.now() - 86400000).toISOString() },
    { id: '3', userId, activityType: 'achievement_earned' as const, title: 'Earned "Collector" badge', description: 'Reached 10 items', metadata: {}, isPublic: true, createdAt: new Date(Date.now() - 172800000).toISOString() },
  ].slice(offset, offset + limit);
}

export async function logActivity(_activityType: string, _title: string, _description?: string, _metadata?: Record<string, unknown>, _isPublic?: boolean): Promise<void> { /* no-op */ }

export async function unifiedSearch(query: string, limit = 5) {
  const q = query.toLowerCase();
  return {
    items: [
      { id: '1', name: 'Charizard Base Set', category: 'pokemon_tcg', imageUrl: null as string | null, price: 450 },
      { id: '2', name: 'Black Lotus', category: 'mtg', imageUrl: null as string | null, price: 25000 },
    ].filter((i) => i.name.toLowerCase().includes(q)).slice(0, limit),
    catalog: [
      { id: 'cat-1', category: 'pokemon_tcg', itemKey: 'base-charizard-holo', title: 'Charizard Holo (Base Set)', brand: 'Pokemon', imageUrl: null as string | null },
      { id: 'cat-2', category: 'mtg', itemKey: 'alpha-black-lotus', title: 'Black Lotus (Alpha)', brand: 'Magic: The Gathering', imageUrl: null as string | null },
      { id: 'cat-3', category: 'lego', itemKey: 'lego-millennium-falcon', title: 'Millennium Falcon UCS', brand: 'LEGO', imageUrl: null as string | null },
    ].filter((c) => c.title.toLowerCase().includes(q)).slice(0, limit),
    users: [
      { id: 'u1', displayName: 'CollectorPro', handle: 'collectorpro', avatarUrl: null as string | null },
    ].filter((u) => u.displayName.toLowerCase().includes(q)).slice(0, limit),
    events: [] as Array<{ id: string; title: string; startDate?: string; location?: string; category?: string }>,
    categories: [] as Array<{ id: string; name: string }>,
  };
}
