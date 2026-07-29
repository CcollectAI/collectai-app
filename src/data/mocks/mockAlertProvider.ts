/**
 * Mock alerts domain provider.
 */

import type { PaginationParams, AlertFeedItem, AlertRule } from '../types';

export async function listAlertsFeed(pagination?: PaginationParams): Promise<AlertFeedItem[]> {
  const now = new Date();
  const mockAlerts: AlertFeedItem[] = [
    {
      id: 'alert-1',
      type: 'price_drop',
      title: 'Price drop on Charizard VMAX',
      body: 'Down 15% from your target price. Now €297 on Cardmarket.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 30).toISOString(),
      watchlistItemId: 'wl-mock-1',
    },
    {
      id: 'alert-2',
      type: 'restock',
      title: 'LEGO UCS Millennium Falcon back in stock',
      body: 'Available at LEGO.com for €849. Limited quantities.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 2).toISOString(),
      watchlistItemId: 'wl-mock-2',
    },
    {
      id: 'alert-3',
      type: 'drop_detected',
      title: 'New Pokémon 151 reprint wave',
      body: 'Booster boxes spotted at distributor. Expected retail arrival: 2 weeks.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 5).toISOString(),
    },
    {
      id: 'alert-4',
      type: 'price_spike',
      title: 'MTG Mox Diamond spiking',
      body: 'Up 22% in the last 48 hours. Current mid: €485.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 8).toISOString(),
      itemId: 'mtg-item-1',
    },
    {
      id: 'alert-5',
      type: 'price_drop',
      title: 'Funko Pop Darth Maul below €200',
      body: 'Holographic variant now at €189 on eBay.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 12).toISOString(),
    },
    {
      id: 'alert-6',
      type: 'completeness',
      title: 'Base Set collection at 85%',
      body: 'You\'re 6 cards away from completing your Base Set 1st Edition collection.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 24).toISOString(),
    },
    {
      id: 'alert-7',
      type: 'restock',
      title: 'Gunpla PG Unicorn restocked',
      body: 'HLJ has stock. Ships internationally.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 26).toISOString(),
    },
    {
      id: 'alert-8',
      type: 'price_drop',
      title: 'Warhammer Knight Castellan -18%',
      body: 'Games Workshop sale. Now €135 (was €165).',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 36).toISOString(),
    },
    {
      id: 'alert-9',
      type: 'rarity',
      title: 'Rare listing detected',
      body: 'PSA 10 Gold Star Umbreon listed on eBay. Only 3rd copy this year.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 48).toISOString(),
    },
    {
      id: 'alert-10',
      type: 'drop_detected',
      title: 'KAWS Companion drop announced',
      body: 'New colorway dropping March 15 on kawsone.com.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 72).toISOString(),
    },
    {
      id: 'alert-11',
      type: 'price_spike',
      title: 'Disney Lorcana Elsa surging',
      body: 'Enchanted foil up 45% this week. Now €89.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 96).toISOString(),
    },
    {
      id: 'alert-12',
      type: 'restock',
      title: 'Hot Wheels RLC membership open',
      body: 'Annual membership now available. Includes exclusive Skyline.',
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 120).toISOString(),
    },
  ];

  if (pagination) {
    const offset = pagination.offset ?? 0;
    const limit = pagination.limit ?? mockAlerts.length;
    return mockAlerts.slice(offset, offset + limit);
  }
  return mockAlerts;
}

/**
 * Mock standing alert rules (GET /alerts/mine). Distinct from the trigger
 * feed above — see the AlertRule doc comment in ../types.ts for why these
 * must not be crossed.
 */
export async function listAlertRules(pagination?: PaginationParams): Promise<AlertRule[]> {
  const now = new Date();
  const rules: AlertRule[] = [
    {
      id: 'rule-1',
      itemId: null,
      category: 'pokemon',
      triggerType: 'below_threshold',
      thresholdValue: 250,
      direction: 'down',
      active: true,
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 24 * 3).toISOString(),
    },
    {
      id: 'rule-2',
      itemId: null,
      category: 'lego',
      triggerType: 'below_threshold',
      thresholdValue: 800,
      direction: 'down',
      active: true,
      createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 24 * 9).toISOString(),
    },
  ];
  const limit = pagination?.limit ?? 20;
  const offset = pagination?.offset ?? 0;
  return rules.slice(offset, offset + limit);
}
