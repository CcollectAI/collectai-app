/**
 * Mock watchlist domain provider.
 */

import type {
  Item,
  WatchlistItem,
  CreateWatchlistInput,
} from '../types';
import { logger } from '@/lib/logger';
import { mockWatchlistItems, setMockWatchlistItems, mockCreatedItems } from './mockState';

export async function listWatchlist(_userId: string): Promise<WatchlistItem[]> {
  return [...mockWatchlistItems].sort((a, b) => {
    const aTime = a.createdAt || '';
    const bTime = b.createdAt || '';
    return bTime.localeCompare(aTime);
  });
}

export async function addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
  const newItem: WatchlistItem = {
    id: `wl-mock-${Date.now()}`,
    title: input.title,
    priority: input.priority || 'medium',
    owned: false,
    targetPrice: input.targetPrice ?? null,
    currency: 'EUR',
    category: input.category,
    notes: input.notes,
    createdAt: new Date().toISOString(),
  };
  mockWatchlistItems.push(newItem);
  logger.info('[MockDataProvider] addWatchlistItem', { id: newItem.id, title: newItem.title });
  return newItem;
}

export async function updateWatchlistItem(id: string, updates: { targetPrice?: number | null; notes?: string; sortOrder?: number }): Promise<WatchlistItem> {
  const item = mockWatchlistItems.find((i) => i.id === id);
  if (!item) throw new Error('Watchlist item not found');
  if (updates.targetPrice !== undefined) item.targetPrice = updates.targetPrice;
  if (updates.notes !== undefined) item.notes = updates.notes;
  if (updates.sortOrder !== undefined) item.sortOrder = updates.sortOrder;
  logger.info('[MockDataProvider] updateWatchlistItem', { id, updates });
  return item;
}

export async function removeWatchlistItem(id: string): Promise<void> {
  const index = mockWatchlistItems.findIndex((item) => item.id === id);
  if (index !== -1) {
    mockWatchlistItems.splice(index, 1);
    logger.info('[MockDataProvider] removeWatchlistItem', { id });
  }
}

export async function removeWatchlistItems(ids: string[]): Promise<void> {
  for (const id of ids) {
    await removeWatchlistItem(id);
  }
}

export async function convertWatchlistToItem(
  watchlistItemId: string,
  actualPrice?: number,
  notes?: string,
): Promise<Item> {
  const watchlistItem = mockWatchlistItems.find((w) => w.id === watchlistItemId);
  if (!watchlistItem) {
    throw new Error(`Watchlist item not found: ${watchlistItemId}`);
  }

  const newItem: Item = {
    id: `item-converted-${Date.now()}`,
    name: watchlistItem.title,
    category: watchlistItem.category || 'Other',
    price: actualPrice ?? watchlistItem.targetPrice ?? 0,
    imageUrl: undefined,
    updatedAt: new Date().toISOString(),
  };

  mockCreatedItems.push(newItem);
  setMockWatchlistItems(mockWatchlistItems.filter((w) => w.id !== watchlistItemId));

  logger.info('[MockDataProvider] convertWatchlistToItem', {
    watchlistItemId,
    actualPrice,
    notes,
    newItemId: newItem.id,
  });

  return newItem;
}
