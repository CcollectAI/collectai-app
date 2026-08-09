/**
 * Mock items domain provider — CRUD on items + quickscan.
 */

import type {
  PaginationParams,
  Item,
  CreateItemInput,
  QuickScanResult,
  QuickscanDraft,
  PersistedItem,
} from '../types';
import { MOCK_TOP_MOVERS } from '../../mockData';
import { logger } from '@/lib/logger';
import { mockCreatedItems } from './mockState';

export async function listItems(pagination?: PaginationParams): Promise<Item[]> {
  const mockItems: Item[] = MOCK_TOP_MOVERS.map((m) => ({
    id: m.id,
    name: m.name,
    category: m.category,
    price: m.value,
    imageUrl: undefined,
    updatedAt: undefined,
  }));

  const all = [...mockItems, ...mockCreatedItems];
  if (pagination) {
    const offset = pagination.offset ?? 0;
    const limit = pagination.limit ?? all.length;
    return all.slice(offset, offset + limit);
  }
  return all;
}

export async function createItem(input: CreateItemInput): Promise<Item> {
  const newItem: Item = {
    id: `mock-${Date.now()}`,
    name: input.name,
    category: input.category,
    price: input.price,
    imageUrl: input.imageUrl,
    updatedAt: new Date().toISOString(),
  };
  mockCreatedItems.push(newItem);
  return newItem;
}

export async function deleteItem(itemId: string): Promise<void> {
  const idx = mockCreatedItems.findIndex((it) => it.id === itemId);
  if (idx !== -1) {
    mockCreatedItems.splice(idx, 1);
  }
}

export async function updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>>): Promise<Item> {
  const idx = mockCreatedItems.findIndex((it) => it.id === itemId);
  if (idx !== -1) {
    const updated = { ...mockCreatedItems[idx], ...patch, updatedAt: new Date().toISOString() };
    mockCreatedItems[idx] = updated;
    return updated;
  }
  // Handle demo/seed items by promoting them into mockCreatedItems
  const demoItem: Item = {
    id: itemId,
    name: patch.name ?? 'Demo Item',
    category: patch.category ?? 'uncategorized',
    price: patch.price ?? 0,
    imageUrl: patch.imageUrl ?? undefined,
    updatedAt: new Date().toISOString(),
  };
  const merged = { ...demoItem, ...patch, updatedAt: new Date().toISOString() };
  mockCreatedItems.push(merged);
  return merged;
}

export async function listArchivedItems(): Promise<Item[]> {
  // The demo fixture has no archived items. [] is the honest answer here, and
  // the screen renders its empty state rather than an error.
  return [];
}

export async function archiveItem(itemId: string): Promise<void> {
  const idx = mockCreatedItems.findIndex((it) => it.id === itemId);
  if (idx !== -1) {
    mockCreatedItems.splice(idx, 1);
  }
}

export async function unarchiveItem(_itemId: string): Promise<void> {
  logger.info('[MockDataProvider] unarchiveItem', { itemId: _itemId });
}

export async function persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
  const id = `mock-qs-${Date.now()}`;
  const createdAt = new Date().toISOString();
  const title = input.title || 'Untitled Scan';
  const categoryId = input.categoryId || 'uncategorized';

  const item: Item = {
    id,
    name: title,
    category: categoryId,
    price: 0,
    imageUrl: input.photoUri,
    updatedAt: createdAt,
  };
  mockCreatedItems.push(item);

  logger.info('[MockDataProvider] persistQuickscanDraft', { id, title, categoryId });

  return {
    id,
    title,
    categoryId,
    createdAt,
    imageUrl: input.photoUri,
  };
}

 
export async function quickscanSingle(_imageUri?: string): Promise<QuickScanResult> {
  return {
    itemId: null,
    attributes: {
      category: 'mtg',
      editionGuess: 'Unlimited',
      conditionGuess: 'Near Mint',
      rarityScore: 0.82,
    },
    prediction: {
      name: 'Demo Black Lotus',
      estimatedLow: 18000.0,
      estimatedMid: 22000.0,
      estimatedHigh: 26000.0,
      currency: 'EUR',
      confidence: 0.91,
      explanation: 'Priced based on excellent condition, rarity, and strong market demand.',
    },
  };
}

export async function searchItems(query: string): Promise<Item[]> {
  if (!query.trim()) return [];

  const allItems = await listItems();
  const lowerQuery = query.toLowerCase();

  return allItems.filter(
    (item) =>
      item.name.toLowerCase().includes(lowerQuery) ||
      item.category.toLowerCase().includes(lowerQuery)
  );
}
