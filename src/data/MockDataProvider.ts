/**
 * MockDataProvider — returns mock/demo data.
 * Reuses existing mock data from src/mockData.ts where possible.
 */

import type { DataProvider } from './DataProvider';
import type {
  PortfolioSummary,
  Item,
  WatchlistItem,
  CreateItemInput,
} from './types';
import {
  MOCK_ANALYTICS_SUMMARY,
  MOCK_TOP_MOVERS,
} from '../mockData';

// In-memory store for created items (persists only during session)
let mockCreatedItems: Item[] = [];

export class MockDataProvider implements DataProvider {
  async getPortfolioSummary(): Promise<PortfolioSummary> {
    // Reuse existing mock data
    return {
      total: MOCK_ANALYTICS_SUMMARY.totalValue,
      deltaPct: MOCK_ANALYTICS_SUMMARY.avgChangePct7d,
      itemCount: MOCK_ANALYTICS_SUMMARY.totalItems,
    };
  }

  async listItems(): Promise<Item[]> {
    // Convert MOCK_TOP_MOVERS to Item shape + any created items
    const mockItems: Item[] = MOCK_TOP_MOVERS.map((m) => ({
      id: m.id,
      name: m.name,
      category: m.category,
      price: m.value,
      imageUrl: undefined,
      updatedAt: undefined,
    }));

    return [...mockItems, ...mockCreatedItems];
  }

  async listWatchlist(_userId: string): Promise<WatchlistItem[]> {
    // Return demo watchlist items
    return [
      {
        id: 'wl-mock-1',
        title: 'Charizard VMAX (Rainbow)',
        priority: 'high',
        owned: false,
        targetPrice: 350,
        currency: 'EUR',
      },
      {
        id: 'wl-mock-2',
        title: 'LEGO UCS Millennium Falcon',
        priority: 'medium',
        owned: false,
        targetPrice: 700,
        currency: 'EUR',
      },
    ];
  }

  async createItem(input: CreateItemInput): Promise<Item> {
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
}

// Singleton instance
export const mockDataProvider = new MockDataProvider();
