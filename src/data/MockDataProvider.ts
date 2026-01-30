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
  QuickScanResult,
  PublicUserProfile,
  CategoryStoreData,
  SpotlightSlide,
  MiniUserProfile,
} from './types';
import { getCategoryById, type Category } from './categories';
import { EVENTS } from './events';
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

  async quickscanSingle(): Promise<QuickScanResult> {
    // Deterministic mock matching backend schema
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
      },
    };
  }

  async searchItems(query: string): Promise<Item[]> {
    if (!query.trim()) return [];

    const allItems = await this.listItems();
    const lowerQuery = query.toLowerCase();

    return allItems.filter(
      (item) =>
        item.name.toLowerCase().includes(lowerQuery) ||
        item.category.toLowerCase().includes(lowerQuery)
    );
  }

  async getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
    // Deterministic mock profiles
    const mockProfiles: Record<string, PublicUserProfile> = {
      'collector-aurora': {
        id: 'collector-aurora',
        displayName: 'Aurora',
        handle: 'aurora.cards',
        avatarUrl: null,
        bio: 'Modern + vintage Pokémon with a side of Disney Lorcana. Collecting like a portfolio, not a pile.',
        interests: ['Pokémon Cards', 'Disney Lorcana', 'Funko Pops'],
        collectionCount: 186,
        collectionValueEur: 12450,
      },
      'collector-rune': {
        id: 'collector-rune',
        displayName: 'Rune',
        handle: 'rune.mtgguy',
        avatarUrl: null,
        bio: 'MTG reserve list and Flesh and Blood legendaries. Plays Commander, collects like a CFO.',
        interests: ['Magic: The Gathering', 'Flesh and Blood'],
        collectionCount: 210,
        collectionValueEur: 18400,
      },
      'collector-mini': {
        id: 'collector-mini',
        displayName: 'Mini Martian',
        handle: 'mini.martian',
        avatarUrl: null,
        bio: 'Warhammer and Gunpla painter. Tracks hobby time and build value as part of the portfolio.',
        interests: ['Warhammer Minis', 'Gunpla & Model Kits'],
        collectionCount: 95,
        collectionValueEur: 6200,
      },
    };

    return mockProfiles[userId] ?? null;
  }

  async getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
    const category = getCategoryById(categoryId);
    if (!category) return null;

    // Mock spotlight slides for this category
    const spotlightSlides: SpotlightSlide[] = [
      {
        id: `${categoryId}-slide-1`,
        title: 'New Releases',
        subtitle: `Fresh ${category.name} drops this week`,
        linkType: 'external',
        linkUrl: category.externalMarketplaces[0]?.url,
      },
      {
        id: `${categoryId}-slide-2`,
        title: 'Top Grails',
        subtitle: 'Most wanted items in the community',
        linkType: 'external',
      },
      {
        id: `${categoryId}-slide-3`,
        title: 'Price Movers',
        subtitle: 'Items trending up this month',
        linkType: 'external',
      },
    ];

    // Filter items by category from mock data
    const allItems = await this.listItems();
    const categoryItems = allItems.filter(
      (item) => item.category.toLowerCase().includes(category.name.toLowerCase().split(' ')[0].toLowerCase())
    );

    // If no items match, create some mock items for this category
    const items: Item[] = categoryItems.length > 0 ? categoryItems : [
      {
        id: `${categoryId}-item-1`,
        name: `${category.name} - Rare Find #1`,
        category: category.name,
        price: 450,
      },
      {
        id: `${categoryId}-item-2`,
        name: `${category.name} - Premium Edition`,
        category: category.name,
        price: 890,
      },
      {
        id: `${categoryId}-item-3`,
        name: `${category.name} - Vintage Classic`,
        category: category.name,
        price: 320,
      },
    ];

    // Filter events by categoryId
    const upcomingEvents = EVENTS
      .filter((e) => e.categoryId === categoryId)
      .map((e) => ({
        id: e.id,
        title: e.title,
        kind: e.kind,
        date: e.date,
        time: e.time,
      }));

    // Mock friends who follow this category
    const friendsWhoFollow: MiniUserProfile[] = [
      {
        id: 'collector-aurora',
        displayName: 'Aurora',
        avatarColor: '#0ea5e9',
      },
      {
        id: 'collector-rune',
        displayName: 'Rune',
        avatarColor: '#22c55e',
      },
      {
        id: 'collector-mini',
        displayName: 'Mini Martian',
        avatarColor: '#f97316',
      },
    ];

    return {
      categoryId: category.id,
      categoryName: category.name,
      categoryTagline: category.tagline,
      bannerImageUrl: category.bannerImageUrl,
      spotlightSlides,
      items,
      upcomingEvents,
      friendsWhoFollow,
    };
  }
}

// Singleton instance
export const mockDataProvider = new MockDataProvider();
