/**
 * MockDataProvider — returns mock/demo data.
 * Reuses existing mock data from src/mockData.ts where possible.
 */

import type { DataProvider } from './DataProvider';
import type {
  PaginationParams,
  PortfolioSummary,
  Item,
  WatchlistItem,
  CreateItemInput,
  CreateWatchlistInput,
  QuickScanResult,
  QuickscanDraft,
  PersistedItem,
  PublicUserProfile,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
  AlertFeedItem,
  SpotlightSlide,
  MiniUserProfile,
  DmThread,
  DmRequest,
  DmMessage,
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  CreateBuildPaintProjectInput,
  BarcodeLookupResult,
  MarketSearchOptions,
  MarketSearchResult,
  MarketHit,
  Offer,
  OfferEvent,
  UserReputation,
} from './types';
import { getCategoryById, CATEGORIES, type Category } from './categories';
import { EVENTS, type CollectorsEvent, type CreateEventInput } from './events';
import {
  MOCK_ANALYTICS_SUMMARY,
  MOCK_TOP_MOVERS,
  MOCK_TWITCH_CREATORS,
} from '../mockData';
import { logger } from '@/lib/logger';

// In-memory store for created items (persists only during session)
let mockCreatedItems: Item[] = [];

// In-memory store for followed categories
const mockFollowedCategories: Set<string> = new Set(['pokemon', 'warhammer', 'lego']);

// In-memory store for event RSVP status
const mockEventAttendees: Map<string, string> = new Map(); // eventId -> status

// In-memory store for owned category items (persists only during session)
const ownedCategoryItems: Set<string> = new Set();

// In-memory watchlist store (persists only during session)
let mockWatchlistItems: WatchlistItem[] = [
  {
    id: 'wl-mock-1',
    title: 'Charizard VMAX (Rainbow)',
    priority: 'high',
    owned: false,
    targetPrice: 350,
    currency: 'EUR',
    category: 'Pokémon',
    notes: 'Grail card, willing to pay up to €400',
    createdAt: '2025-12-10T10:00:00Z',
  },
  {
    id: 'wl-mock-2',
    title: 'LEGO UCS Millennium Falcon 75192',
    priority: 'medium',
    owned: false,
    targetPrice: 700,
    currency: 'EUR',
    category: 'LEGO',
    notes: 'Birthday gift idea',
    createdAt: '2025-12-08T15:30:00Z',
  },
  {
    id: 'wl-mock-3',
    title: 'Black Lotus (Unlimited)',
    priority: 'high',
    owned: false,
    targetPrice: 8500,
    currency: 'EUR',
    category: 'Magic: The Gathering',
    notes: 'Dream card — only buy if LP or better',
    createdAt: '2025-12-05T09:00:00Z',
  },
  {
    id: 'wl-mock-4',
    title: 'Air Jordan 1 Retro High OG Chicago',
    priority: 'medium',
    owned: false,
    targetPrice: 420,
    currency: 'EUR',
    category: 'Sneakers',
    notes: 'Size 10.5 US, deadstock only',
    createdAt: '2025-11-28T18:00:00Z',
  },
  {
    id: 'wl-mock-5',
    title: 'Warhammer 40K Leviathan Box Set',
    priority: 'low',
    owned: false,
    targetPrice: 150,
    currency: 'EUR',
    category: 'Warhammer',
    notes: 'Good starter set for Tyranids army',
    createdAt: '2025-11-20T12:00:00Z',
  },
  {
    id: 'wl-mock-6',
    title: 'PSA 10 1st Edition Lugia Neo Genesis',
    priority: 'high',
    owned: false,
    targetPrice: 12000,
    currency: 'EUR',
    category: 'Pokémon',
    notes: 'Investment piece — wait for dip below 12k',
    createdAt: '2025-11-15T08:00:00Z',
  },
  {
    id: 'wl-mock-7',
    title: 'Bandai RG Sazabi 1/144',
    priority: 'low',
    owned: false,
    targetPrice: 55,
    currency: 'EUR',
    category: 'Gunpla',
    notes: 'Next build project after current kit',
    createdAt: '2025-11-10T14:00:00Z',
  },
];

// In-memory DM state (persists only during session)
const mockDmThreads: Map<string, DmThread> = new Map([
  ['thread-aurora-rune', {
    id: 'thread-aurora-rune',
    otherUserId: 'collector-rune',
    otherUserName: 'Rune',
    otherUserHandle: 'rune.mtgguy',
    otherUserAvatarUrl: null,
    otherUserAvatarColor: '#22c55e',
    status: 'accepted',
    lastMessagePreview: 'That MTG deal sounds great! Let me know when you want to meet up.',
    lastMessageAt: '2025-12-15T14:30:00Z',
    unreadCount: 1,
    isIncoming: false,
  }],
  ['thread-aurora-mini', {
    id: 'thread-aurora-mini',
    otherUserId: 'collector-mini',
    otherUserName: 'Mini Martian',
    otherUserHandle: 'mini.martian',
    otherUserAvatarUrl: null,
    otherUserAvatarColor: '#f97316',
    status: 'accepted',
    lastMessagePreview: 'Your Warhammer paint job looks amazing!',
    lastMessageAt: '2025-12-14T18:45:00Z',
    unreadCount: 0,
    isIncoming: true,
  }],
]);

const mockDmRequests: Map<string, DmRequest> = new Map([
  ['thread-pending-1', {
    threadId: 'thread-pending-1',
    fromUserId: 'collector-alex',
    fromUserName: 'Alex TCG',
    fromUserHandle: 'alex.tcg',
    fromUserAvatarUrl: null,
    fromUserAvatarColor: '#8b5cf6',
    requestMessage: 'Hey! Saw you at the Amsterdam meetup. Want to trade some Pokémon cards?',
    requestedAt: '2025-12-16T10:00:00Z',
  }],
]);

const mockDmMessages: Map<string, DmMessage[]> = new Map([
  ['thread-aurora-rune', [
    {
      id: 'msg-1',
      threadId: 'thread-aurora-rune',
      authorUserId: 'collector-aurora',
      text: 'Hey Rune! I noticed you have some MTG reserve list cards. Interested in any trades?',
      createdAt: '2025-12-15T12:00:00Z',
    },
    {
      id: 'msg-2',
      threadId: 'thread-aurora-rune',
      authorUserId: 'collector-rune',
      text: 'That MTG deal sounds great! Let me know when you want to meet up.',
      createdAt: '2025-12-15T14:30:00Z',
    },
  ]],
  ['thread-aurora-mini', [
    {
      id: 'msg-3',
      threadId: 'thread-aurora-mini',
      authorUserId: 'collector-mini',
      text: 'Your Warhammer paint job looks amazing!',
      createdAt: '2025-12-14T18:45:00Z',
    },
  ]],
]);

// In-memory blocked users store
const mockBlockedUsers: Set<string> = new Set();

// Track DM status by other user ID (for getDmStatus)
const mockDmStatusByUser: Map<string, 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> = new Map([
  ['collector-rune', 'accepted'],
  ['collector-mini', 'accepted'],
  ['collector-alex', 'pending_incoming'],
]);

// In-memory build & paint projects store
const mockBuildPaintProjects: Map<string, BuildPaintProject> = new Map([
  ['bp-mock-1', {
    id: 'bp-mock-1',
    title: 'Warhammer Kill Team squad',
    category: 'Warhammer minis',
    categoryId: 'warhammer',
    status: 'active',
    percent: 40,
    isCompleted: false,
    notes: 'Urban camo scheme with some neon accents',
    createdAt: '2025-12-01T10:00:00Z',
    updatedAt: '2025-12-15T14:00:00Z',
  }],
  ['bp-mock-2', {
    id: 'bp-mock-2',
    title: 'Gunpla MG RX-78-2 (Ver. 3.0)',
    category: 'Gunpla & model kits',
    categoryId: 'gunpla',
    status: 'active',
    percent: 65,
    isCompleted: false,
    notes: 'Panel lining + decals this weekend',
    createdAt: '2025-11-20T08:00:00Z',
    updatedAt: '2025-12-14T18:00:00Z',
  }],
  ['bp-mock-3', {
    id: 'bp-mock-3',
    title: 'LEGO UCS Millennium Falcon',
    category: 'Bricks & kits',
    categoryId: 'lego',
    status: 'completed',
    percent: 100,
    isCompleted: true,
    notes: 'Display-only; tracking for nostalgia',
    createdAt: '2025-10-01T12:00:00Z',
    updatedAt: '2025-11-15T16:00:00Z',
  }],
  ['bp-mock-4', {
    id: 'bp-mock-4',
    title: 'Blood Angels Sanguinary Guard',
    category: 'Warhammer minis',
    categoryId: 'warhammer',
    status: 'backlog',
    percent: 0,
    isCompleted: false,
    notes: null,
    createdAt: '2025-12-10T09:00:00Z',
    updatedAt: '2025-12-10T09:00:00Z',
  }],
]);

// In-memory build paint steps
const mockBuildPaintSteps: Map<string, BuildPaintStep[]> = new Map([
  ['bp-mock-1', [
    { id: 'step-1-1', projectId: 'bp-mock-1', title: 'Assemble all models', isDone: true, sortOrder: 1, createdAt: '2025-12-01T10:00:00Z' },
    { id: 'step-1-2', projectId: 'bp-mock-1', title: 'Prime with airbrush', isDone: true, sortOrder: 2, createdAt: '2025-12-02T10:00:00Z' },
    { id: 'step-1-3', projectId: 'bp-mock-1', title: 'Base coat armor', isDone: false, sortOrder: 3, createdAt: '2025-12-05T10:00:00Z' },
    { id: 'step-1-4', projectId: 'bp-mock-1', title: 'Details and highlights', isDone: false, sortOrder: 4, createdAt: '2025-12-05T10:00:00Z' },
    { id: 'step-1-5', projectId: 'bp-mock-1', title: 'Basing and varnish', isDone: false, sortOrder: 5, createdAt: '2025-12-05T10:00:00Z' },
  ]],
  ['bp-mock-2', [
    { id: 'step-2-1', projectId: 'bp-mock-2', title: 'Snap fit assembly', isDone: true, sortOrder: 1, createdAt: '2025-11-20T08:00:00Z' },
    { id: 'step-2-2', projectId: 'bp-mock-2', title: 'Panel lining', isDone: true, sortOrder: 2, createdAt: '2025-11-25T08:00:00Z' },
    { id: 'step-2-3', projectId: 'bp-mock-2', title: 'Apply decals', isDone: false, sortOrder: 3, createdAt: '2025-12-01T08:00:00Z' },
    { id: 'step-2-4', projectId: 'bp-mock-2', title: 'Top coat', isDone: false, sortOrder: 4, createdAt: '2025-12-01T08:00:00Z' },
  ]],
]);

// In-memory build paint notes
const mockBuildPaintNotes: Map<string, BuildPaintNote[]> = new Map([
  ['bp-mock-1', [
    { id: 'note-1-1', projectId: 'bp-mock-1', body: 'Decided on urban camo pattern - grey base with dark grey camo stripes', createdAt: '2025-12-01T11:00:00Z' },
    { id: 'note-1-2', projectId: 'bp-mock-1', body: 'Zenithal prime worked great. Using Vallejo German Grey as base.', createdAt: '2025-12-03T14:00:00Z' },
  ]],
  ['bp-mock-2', [
    { id: 'note-2-1', projectId: 'bp-mock-2', body: 'Using Tamiya Panel Line Accent - brown for white parts, black for dark parts', createdAt: '2025-11-26T10:00:00Z' },
  ]],
]);

export class MockDataProvider implements DataProvider {
  async getPortfolioSummary(): Promise<PortfolioSummary> {
    // Reuse existing mock data
    return {
      total: MOCK_ANALYTICS_SUMMARY.totalValue,
      deltaPct: MOCK_ANALYTICS_SUMMARY.avgChangePct7d,
      itemCount: MOCK_ANALYTICS_SUMMARY.totalItems,
    };
  }

  async listItems(pagination?: PaginationParams): Promise<Item[]> {
    // Convert MOCK_TOP_MOVERS to Item shape + any created items
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

  async listWatchlist(_userId: string): Promise<WatchlistItem[]> {
    // Return in-memory watchlist items (sorted by createdAt desc)
    return [...mockWatchlistItems].sort((a, b) => {
      const aTime = a.createdAt || '';
      const bTime = b.createdAt || '';
      return bTime.localeCompare(aTime);
    });
  }

  async addWatchlistItem(input: CreateWatchlistInput): Promise<WatchlistItem> {
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

  async updateWatchlistItem(id: string, updates: { targetPrice?: number | null; notes?: string }): Promise<WatchlistItem> {
    const item = mockWatchlistItems.find((i) => i.id === id);
    if (!item) throw new Error('Watchlist item not found');
    if (updates.targetPrice !== undefined) item.targetPrice = updates.targetPrice;
    if (updates.notes !== undefined) item.notes = updates.notes;
    logger.info('[MockDataProvider] updateWatchlistItem', { id, updates });
    return item;
  }

  async removeWatchlistItem(id: string): Promise<void> {
    const index = mockWatchlistItems.findIndex((item) => item.id === id);
    if (index !== -1) {
      mockWatchlistItems.splice(index, 1);
      logger.info('[MockDataProvider] removeWatchlistItem', { id });
    }
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

  async deleteItem(itemId: string): Promise<void> {
    const idx = mockCreatedItems.findIndex((it) => it.id === itemId);
    if (idx !== -1) {
      mockCreatedItems.splice(idx, 1);
    }
  }

  async updateItem(itemId: string, patch: Partial<Pick<Item, 'name' | 'category' | 'price' | 'imageUrl'>>): Promise<Item> {
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

  async archiveItem(itemId: string): Promise<void> {
    const idx = mockCreatedItems.findIndex((it) => it.id === itemId);
    if (idx !== -1) {
      mockCreatedItems.splice(idx, 1);
    }
  }

  async unarchiveItem(_itemId: string): Promise<void> {
    // Mock: no-op (items aren't really archived in mock mode)
    logger.info('[MockDataProvider] unarchiveItem', { itemId: _itemId });
  }

  async persistQuickscanDraft(input: QuickscanDraft): Promise<PersistedItem> {
    const id = `mock-qs-${Date.now()}`;
    const createdAt = new Date().toISOString();
    const title = input.title || 'Untitled Scan';
    const categoryId = input.categoryId || 'uncategorized';

    // Also add to mockCreatedItems so it shows up in listItems/portfolio
    const item: Item = {
      id,
      name: title,
      category: categoryId,
      price: 0, // No pricing in this slice
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

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async quickscanSingle(_imageUri?: string): Promise<QuickScanResult> {
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
        explanation: 'Priced based on excellent condition, rarity, and strong market demand.',
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

  async getMyProfile(): Promise<PublicUserProfile | null> {
    // Mock current user is 'collector-aurora'
    return this.getPublicUserProfile('collector-aurora');
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

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Browsing (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  async listCategorySummaries(): Promise<CategorySummary[]> {
    // Generate mock summaries from static CATEGORIES
    return CATEGORIES.map((cat, idx) => {
      // Vary completion for visual interest (cap at 95% to stay realistic)
      const totalCount = 50 + idx * 15;
      const pct = Math.min(0.3 + idx * 0.04, 0.95);
      const ownedCount = Math.floor(totalCount * pct);
      const missingCount = totalCount - ownedCount;
      const completionPct = Math.round((ownedCount / totalCount) * 100);

      return {
        id: cat.id,
        name: cat.name,
        completionPct,
        ownedCount,
        missingCount,
        totalCount,
      };
    });
  }

  async listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
    const category = getCategoryById(categoryId);
    if (!category) return [];

    // Generate 5-12 mock missing items based on category
    const mockMissingItems: Record<string, CategoryMissingItem[]> = {
      pokemon: [
        { id: 'pkmn-m1', categoryId, title: 'Charizard VMAX (Rainbow)', brand: 'Pokémon TCG', notes: 'Sword & Shield era grail' },
        { id: 'pkmn-m2', categoryId, title: 'Pikachu Illustrator', brand: 'Pokémon TCG', notes: 'Ultra rare promo' },
        { id: 'pkmn-m3', categoryId, title: 'Base Set 1st Ed Booster Box', brand: 'Pokémon TCG', notes: 'Sealed vintage' },
        { id: 'pkmn-m4', categoryId, title: 'Moonbreon (Alt Art)', brand: 'Pokémon TCG', notes: 'Evolving Skies chase' },
        { id: 'pkmn-m5', categoryId, title: 'Gold Star Umbreon', brand: 'Pokémon TCG', notes: 'POP Series rare' },
        { id: 'pkmn-m6', categoryId, title: 'Shiny Mew VMAX', brand: 'Pokémon TCG', notes: 'Celebrations subset' },
      ],
      funko: [
        { id: 'funko-m1', categoryId, title: 'Metallic Blue Batman #01', brand: 'Funko', notes: 'SDCC 2010 Exclusive' },
        { id: 'funko-m2', categoryId, title: 'Holographic Darth Maul', brand: 'Funko', notes: 'Paris Comic Con' },
        { id: 'funko-m3', categoryId, title: 'Clockwork Orange Alex', brand: 'Funko', notes: 'Vaulted 2013' },
        { id: 'funko-m4', categoryId, title: 'Glow Headless Ned Stark', brand: 'Funko', notes: 'SDCC Exclusive' },
        { id: 'funko-m5', categoryId, title: 'Planet Arlia Vegeta', brand: 'Funko', notes: 'Toy Tokyo grail' },
      ],
      mtg: [
        { id: 'mtg-m1', categoryId, title: 'Black Lotus (Beta)', brand: 'MTG', notes: 'Power Nine' },
        { id: 'mtg-m2', categoryId, title: 'Ancestral Recall (Beta)', brand: 'MTG', notes: 'Power Nine' },
        { id: 'mtg-m3', categoryId, title: 'Underground Sea (Rev)', brand: 'MTG', notes: 'Dual land' },
        { id: 'mtg-m4', categoryId, title: 'Tabernacle at Pendrell Vale', brand: 'MTG', notes: 'Reserved list' },
        { id: 'mtg-m5', categoryId, title: 'Gaea\'s Cradle', brand: 'MTG', notes: 'Commander staple' },
        { id: 'mtg-m6', categoryId, title: 'Mox Diamond', brand: 'MTG', notes: 'Reserved list' },
        { id: 'mtg-m7', categoryId, title: 'Lion\'s Eye Diamond', brand: 'MTG', notes: 'Legacy combo piece' },
      ],
      warhammer: [
        { id: 'wh-m1', categoryId, title: 'Primarch Roboute Guilliman', brand: 'Games Workshop', notes: 'Forge World resin' },
        { id: 'wh-m2', categoryId, title: 'Knight Castellan', brand: 'Games Workshop', notes: 'Imperial Knights' },
        { id: 'wh-m3', categoryId, title: 'Mortarion Daemon Primarch', brand: 'Games Workshop', notes: 'Death Guard centerpiece' },
        { id: 'wh-m4', categoryId, title: 'Warlord Titan', brand: 'Forge World', notes: 'Adeptus Titanicus scale' },
        { id: 'wh-m5', categoryId, title: 'Blood Angels Sanguinor', brand: 'Games Workshop', notes: 'Chapter hero' },
      ],
      designer_toys: [
        { id: 'dt-m1', categoryId, title: 'KAWS Companion (Grey)', brand: 'KAWS', notes: 'Open Edition 2016' },
        { id: 'dt-m2', categoryId, title: 'Bearbrick 1000% Basquiat', brand: 'Medicom', notes: 'Art collab' },
        { id: 'dt-m3', categoryId, title: 'Superplastic Janky', brand: 'Superplastic', notes: 'Artist series' },
        { id: 'dt-m4', categoryId, title: 'Ron English Grin', brand: 'Made by Monsters', notes: 'Limited sofubi' },
        { id: 'dt-m5', categoryId, title: 'Coarse Noop (Cloud)', brand: 'Coarse', notes: 'Colorway exclusive' },
        { id: 'dt-m6', categoryId, title: 'James Jean Azimuth', brand: 'Good Smile', notes: 'First vinyl' },
      ],
    };

    // Return category-specific items or generate generic ones
    let items: CategoryMissingItem[];
    if (mockMissingItems[categoryId]) {
      items = mockMissingItems[categoryId];
    } else {
      // Generic missing items for categories without specific mock data
      items = Array.from({ length: 8 }, (_, i) => ({
        id: `${categoryId}-missing-${i + 1}`,
        categoryId,
        title: `${category.name} Item #${i + 1}`,
        brand: category.name,
        notes: i % 2 === 0 ? 'Rare variant' : null,
      }));
    }

    // Filter out items that have been marked as owned
    return items.filter((item) => !ownedCategoryItems.has(item.id));
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Alerts Feed (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  async listAlertsFeed(pagination?: PaginationParams): Promise<AlertFeedItem[]> {
    // Return 12 demo alerts with mixed types
    const now = new Date();
    const mockAlerts: AlertFeedItem[] = [
      {
        id: 'alert-1',
        type: 'price_drop',
        title: 'Price drop on Charizard VMAX',
        body: 'Down 15% from your target price. Now €297 on Cardmarket.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 30).toISOString(), // 30 min ago
        watchlistItemId: 'wl-mock-1',
      },
      {
        id: 'alert-2',
        type: 'restock',
        title: 'LEGO UCS Millennium Falcon back in stock',
        body: 'Available at LEGO.com for €849. Limited quantities.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
        watchlistItemId: 'wl-mock-2',
      },
      {
        id: 'alert-3',
        type: 'drop_detected',
        title: 'New Pokémon 151 reprint wave',
        body: 'Booster boxes spotted at distributor. Expected retail arrival: 2 weeks.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 5).toISOString(), // 5 hours ago
      },
      {
        id: 'alert-4',
        type: 'price_spike',
        title: 'MTG Mox Diamond spiking',
        body: 'Up 22% in the last 48 hours. Current mid: €485.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 8).toISOString(), // 8 hours ago
        itemId: 'mtg-item-1',
      },
      {
        id: 'alert-5',
        type: 'price_drop',
        title: 'Funko Pop Darth Maul below €200',
        body: 'Holographic variant now at €189 on eBay.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 12).toISOString(), // 12 hours ago
      },
      {
        id: 'alert-6',
        type: 'completeness',
        title: 'Base Set collection at 85%',
        body: 'You\'re 6 cards away from completing your Base Set 1st Edition collection.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
      },
      {
        id: 'alert-7',
        type: 'restock',
        title: 'Gunpla PG Unicorn restocked',
        body: 'HLJ has stock. Ships internationally.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 26).toISOString(), // 26 hours ago
      },
      {
        id: 'alert-8',
        type: 'price_drop',
        title: 'Warhammer Knight Castellan -18%',
        body: 'Games Workshop sale. Now €135 (was €165).',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 36).toISOString(), // 36 hours ago
      },
      {
        id: 'alert-9',
        type: 'rarity',
        title: 'Rare listing detected',
        body: 'PSA 10 Gold Star Umbreon listed on eBay. Only 3rd copy this year.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 48).toISOString(), // 2 days ago
      },
      {
        id: 'alert-10',
        type: 'drop_detected',
        title: 'KAWS Companion drop announced',
        body: 'New colorway dropping March 15 on kawsone.com.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 72).toISOString(), // 3 days ago
      },
      {
        id: 'alert-11',
        type: 'price_spike',
        title: 'Disney Lorcana Elsa surging',
        body: 'Enchanted foil up 45% this week. Now €89.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 96).toISOString(), // 4 days ago
      },
      {
        id: 'alert-12',
        type: 'restock',
        title: 'Hot Wheels RLC membership open',
        body: 'Annual membership now available. Includes exclusive Skyline.',
        createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 120).toISOString(), // 5 days ago
      },
    ];

    if (pagination) {
      const offset = pagination.offset ?? 0;
      const limit = pagination.limit ?? mockAlerts.length;
      return mockAlerts.slice(offset, offset + limit);
    }
    return mockAlerts;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // DM / Inbox methods
  // ─────────────────────────────────────────────────────────────────────────────

  async listInboxThreads(): Promise<DmThread[]> {
    // Return accepted + pending outgoing threads sorted by last message
    const threads = Array.from(mockDmThreads.values())
      .filter((t) => t.status === 'accepted' || (t.status === 'pending' && !t.isIncoming))
      .sort((a, b) => {
        const aTime = a.lastMessageAt || '';
        const bTime = b.lastMessageAt || '';
        return bTime.localeCompare(aTime);
      });
    return threads;
  }

  async listIncomingRequests(): Promise<DmRequest[]> {
    return Array.from(mockDmRequests.values()).sort((a, b) =>
      b.requestedAt.localeCompare(a.requestedAt)
    );
  }

  async requestDm(toUserId: string, message?: string): Promise<string> {
    const threadId = `thread-mock-${Date.now()}`;

    // Create pending thread
    const thread: DmThread = {
      id: threadId,
      otherUserId: toUserId,
      otherUserName: toUserId, // Would normally look up
      otherUserHandle: null,
      otherUserAvatarUrl: null,
      otherUserAvatarColor: '#6b7280',
      status: 'pending',
      lastMessagePreview: message || null,
      lastMessageAt: new Date().toISOString(),
      unreadCount: 0,
      isIncoming: false,
    };

    mockDmThreads.set(threadId, thread);
    mockDmStatusByUser.set(toUserId, 'pending_outgoing');

    logger.info('[MockDataProvider] requestDm', { threadId, toUserId, message });
    return threadId;
  }

  async decideDmRequest(threadId: string, accept: boolean): Promise<void> {
    const request = mockDmRequests.get(threadId);
    if (request) {
      mockDmRequests.delete(threadId);

      if (accept) {
        // Create accepted thread
        const thread: DmThread = {
          id: threadId,
          otherUserId: request.fromUserId,
          otherUserName: request.fromUserName,
          otherUserHandle: request.fromUserHandle,
          otherUserAvatarUrl: request.fromUserAvatarUrl,
          otherUserAvatarColor: request.fromUserAvatarColor,
          status: 'accepted',
          lastMessagePreview: request.requestMessage,
          lastMessageAt: request.requestedAt,
          unreadCount: 1,
          isIncoming: true,
        };
        mockDmThreads.set(threadId, thread);
        mockDmStatusByUser.set(request.fromUserId, 'accepted');

        // Add initial message
        mockDmMessages.set(threadId, [{
          id: `msg-${Date.now()}`,
          threadId,
          authorUserId: request.fromUserId,
          text: request.requestMessage || 'Hi!',
          createdAt: request.requestedAt,
        }]);
      } else {
        mockDmStatusByUser.set(request.fromUserId, 'declined');
      }
    }

    logger.info('[MockDataProvider] decideDmRequest', { threadId, accept });
  }

  async markThreadRead(threadId: string): Promise<void> {
    const thread = mockDmThreads.get(threadId);
    if (thread) {
      thread.unreadCount = 0;
      mockDmThreads.set(threadId, thread);
    }
    logger.info('[MockDataProvider] markThreadRead', { threadId });
  }

  async getThreadMessages(threadId: string): Promise<DmMessage[]> {
    return mockDmMessages.get(threadId) || [];
  }

  async sendMessage(threadId: string, body: string): Promise<DmMessage> {
    // Create new message (current user is collector-aurora in mock)
    const newMessage: DmMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      threadId,
      authorUserId: 'collector-aurora',
      text: body,
      createdAt: new Date().toISOString(),
    };

    // Append to thread messages
    const existing = mockDmMessages.get(threadId) || [];
    mockDmMessages.set(threadId, [...existing, newMessage]);

    // Update thread preview
    const thread = mockDmThreads.get(threadId);
    if (thread) {
      thread.lastMessagePreview = body;
      thread.lastMessageAt = newMessage.createdAt;
      mockDmThreads.set(threadId, thread);
    }

    logger.info('[MockDataProvider] sendMessage', { threadId, body, messageId: newMessage.id });
    return newMessage;
  }

  async setTyping(_threadId: string): Promise<void> {
    // No-op in mock
  }

  async clearTyping(_threadId: string): Promise<void> {
    // No-op in mock
  }

  async isOtherUserTyping(_threadId: string): Promise<boolean> {
    return false;
  }

  async getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> {
    return mockDmStatusByUser.get(otherUserId) || 'none';
  }

  async getInboxUnreadCount(): Promise<number> {
    // Sum unread from threads + count of incoming requests
    const threadUnread = Array.from(mockDmThreads.values())
      .filter((t) => t.status === 'accepted')
      .reduce((sum, t) => sum + t.unreadCount, 0);
    const requestCount = mockDmRequests.size;
    return threadUnread + requestCount;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Analytics
  // ─────────────────────────────────────────────────────────────────────────────

  async getAnalyticsMetrics(): Promise<AnalyticsMetrics> {
    // Compute from actual mock projects
    const projects = Array.from(mockBuildPaintProjects.values());
    const activeProjects = projects.filter((p) => p.status === 'active').length;
    const backlogProjects = projects.filter((p) => p.status === 'backlog').length;
    const completedProjects = projects.filter((p) => p.isCompleted).length;
    const totalBuildMinutes = 1260; // ~21 hours (mock)
    const totalBuildHours = totalBuildMinutes / 60;

    // Use MOCK_TWITCH_CREATORS for Twitch stats
    const twitchCreatorsTracked = MOCK_TWITCH_CREATORS.length;
    const twitchCreatorsLive = MOCK_TWITCH_CREATORS.filter((c) => c.liveNow).length;

    return {
      activeProjects,
      backlogProjects,
      completedProjects,
      totalBuildMinutes,
      totalBuildHours,
      twitchCreatorsTracked,
      twitchCreatorsLive,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Build & Paint Projects
  // ─────────────────────────────────────────────────────────────────────────────

  async listBuildPaintProjects(): Promise<BuildPaintProject[]> {
    return Array.from(mockBuildPaintProjects.values()).sort((a, b) =>
      b.updatedAt.localeCompare(a.updatedAt)
    );
  }

  async createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
    const id = `bp-mock-${Date.now()}`;
    const now = new Date().toISOString();
    const project: BuildPaintProject = {
      id,
      title: input.title,
      category: input.category || null,
      categoryId: input.categoryId || null,
      itemId: input.itemId || null,
      status: 'backlog',
      percent: 0,
      isCompleted: false,
      notes: null,
      createdAt: now,
      updatedAt: now,
    };
    mockBuildPaintProjects.set(id, project);
    mockBuildPaintSteps.set(id, []);
    mockBuildPaintNotes.set(id, []);
    logger.info('[MockDataProvider] createBuildPaintProject', { id, title: input.title });
    return project;
  }

  async setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
    const project = mockBuildPaintProjects.get(projectId);
    if (!project) return;

    project.percent = Math.max(0, Math.min(100, percent));
    if (status) project.status = status;
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
    logger.info('[MockDataProvider] setBuildPaintProgress', { projectId, percent, status });
  }

  async markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
    const project = mockBuildPaintProjects.get(projectId);
    if (!project) return;

    project.isCompleted = isCompleted;
    project.status = isCompleted ? 'completed' : 'active';
    if (isCompleted) project.percent = 100;
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
    logger.info('[MockDataProvider] markBuildPaintProjectComplete', { projectId, isCompleted });
  }

  async listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]> {
    const steps = mockBuildPaintSteps.get(projectId) || [];
    return [...steps].sort((a, b) => a.sortOrder - b.sortOrder);
  }

  async addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep> {
    const steps = mockBuildPaintSteps.get(projectId) || [];
    const sortOrder = steps.length > 0 ? Math.max(...steps.map((s) => s.sortOrder)) + 1 : 1;
    const step: BuildPaintStep = {
      id: `step-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      projectId,
      title,
      isDone: false,
      sortOrder,
      createdAt: new Date().toISOString(),
    };
    steps.push(step);
    mockBuildPaintSteps.set(projectId, steps);
    // Touch project
    const project = mockBuildPaintProjects.get(projectId);
    if (project) {
      project.updatedAt = new Date().toISOString();
      mockBuildPaintProjects.set(projectId, project);
    }
    logger.info('[MockDataProvider] addBuildPaintStep', { projectId, title, stepId: step.id });
    return step;
  }

  async toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void> {
    const entries = Array.from(mockBuildPaintSteps.entries());
    for (let i = 0; i < entries.length; i++) {
      const [projectId, steps] = entries[i];
      const step = steps.find((s) => s.id === stepId);
      if (step) {
        step.isDone = isDone;
        // Touch project
        const project = mockBuildPaintProjects.get(projectId);
        if (project) {
          project.updatedAt = new Date().toISOString();
          mockBuildPaintProjects.set(projectId, project);
        }
        logger.info('[MockDataProvider] toggleBuildPaintStep', { stepId, isDone });
        return;
      }
    }
  }

  async listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]> {
    const notes = mockBuildPaintNotes.get(projectId) || [];
    return [...notes].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote> {
    const notes = mockBuildPaintNotes.get(projectId) || [];
    const note: BuildPaintNote = {
      id: `note-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      projectId,
      body,
      createdAt: new Date().toISOString(),
    };
    notes.push(note);
    mockBuildPaintNotes.set(projectId, notes);
    // Touch project
    const project = mockBuildPaintProjects.get(projectId);
    if (project) {
      project.updatedAt = new Date().toISOString();
      mockBuildPaintProjects.set(projectId, project);
    }
    logger.info('[MockDataProvider] addBuildPaintNote', { projectId, noteId: note.id });
    return note;
  }

  async listBuildPaintProjectsByCategory(categoryId: string): Promise<BuildPaintProject[]> {
    const all = await this.listBuildPaintProjects();
    return all.filter((p) => p.categoryId === categoryId);
  }

  async listBuildPaintProjectsByItem(itemId: string): Promise<BuildPaintProject[]> {
    const all = await this.listBuildPaintProjects();
    return all.filter((p) => p.itemId === itemId);
  }

  async applyStepTemplate(projectId: string, categoryId: string): Promise<BuildPaintStep[]> {
    const { getStepTemplateForCategory } = await import('../constants/buildStepTemplates');
    const template = getStepTemplateForCategory(categoryId);
    const steps: BuildPaintStep[] = [];
    for (const s of template.steps) {
      const step = await this.addBuildPaintStep(projectId, s.label);
      steps.push(step);
    }
    return steps;
  }

  async updateBuildPaintProject(projectId: string, patch: { paintRecipes?: unknown[] }): Promise<void> {
    const project = mockBuildPaintProjects.get(projectId);
    if (project && patch.paintRecipes !== undefined) {
      (project as Record<string, unknown>).paintRecipes = patch.paintRecipes;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Feedback
  // ─────────────────────────────────────────────────────────────────────────────

  async submitFeedback(
    itemId: string,
    feedbackType: 'sale_price' | 'disagree' | 'accurate',
    value?: string,
  ): Promise<{ success: boolean; feedbackId?: string }> {
    const feedbackId = `feedback-mock-${Date.now()}`;
    logger.info('[MockDataProvider] submitFeedback', { itemId, feedbackType, value, feedbackId });
    return { success: true, feedbackId };
  }

  async submitCorrection(
    itemId: string,
    corrections: {
      correctedPrice?: number;
      correctedCondition?: string;
      correctedCategory?: string;
      notes?: string;
    },
  ): Promise<{ success: boolean }> {
    logger.info('[MockDataProvider] submitCorrection', { itemId, corrections });
    return { success: true };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Ownership
  // ─────────────────────────────────────────────────────────────────────────────

  async markCategoryItemOwned(
    categoryItemId: string,
    quantity: number = 1,
    notes?: string,
  ): Promise<{ success: boolean }> {
    logger.info('[MockDataProvider] markCategoryItemOwned', { categoryItemId, quantity, notes });
    // Track the owned item in memory
    ownedCategoryItems.add(categoryItemId);
    return { success: true };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Watchlist → Portfolio Conversion
  // ─────────────────────────────────────────────────────────────────────────────

  async convertWatchlistToItem(
    watchlistItemId: string,
    actualPrice?: number,
    notes?: string,
  ): Promise<Item> {
    // Find the watchlist item
    const watchlistItem = mockWatchlistItems.find((w) => w.id === watchlistItemId);
    if (!watchlistItem) {
      throw new Error(`Watchlist item not found: ${watchlistItemId}`);
    }

    // Create the portfolio item from watchlist data
    const newItem: Item = {
      id: `item-converted-${Date.now()}`,
      name: watchlistItem.title,
      category: watchlistItem.category || 'Other',
      price: actualPrice ?? watchlistItem.targetPrice ?? 0,
      imageUrl: undefined,
      updatedAt: new Date().toISOString(),
    };

    // Add to portfolio
    mockCreatedItems.push(newItem);

    // Remove from watchlist
    mockWatchlistItems = mockWatchlistItems.filter((w) => w.id !== watchlistItemId);

    logger.info('[MockDataProvider] convertWatchlistToItem', {
      watchlistItemId,
      actualPrice,
      notes,
      newItemId: newItem.id,
    });

    return newItem;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Following
  // ─────────────────────────────────────────────────────────────────────────────

  async followCategory(categoryId: string): Promise<void> {
    mockFollowedCategories.add(categoryId);
    logger.info('[MockDataProvider] followCategory', { categoryId });
  }

  async unfollowCategory(categoryId: string): Promise<void> {
    mockFollowedCategories.delete(categoryId);
    logger.info('[MockDataProvider] unfollowCategory', { categoryId });
  }

  async listFollowedCategories(): Promise<string[]> {
    return Array.from(mockFollowedCategories);
  }

  async isFollowingCategory(categoryId: string): Promise<boolean> {
    return mockFollowedCategories.has(categoryId);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────────

  async getEventById(eventId: string): Promise<CollectorsEvent | null> {
    const event = EVENTS.find((e) => e.id === eventId);
    return event ?? null;
  }

  async listEvents(pagination?: PaginationParams): Promise<CollectorsEvent[]> {
    // Filter to followed categories (mock personalization)
    const followed = mockFollowedCategories;
    const all = [...EVENTS]
      .filter((e) => !e.categoryId || followed.has(e.categoryId))
      .map((e) => ({
        ...e,
        attendeeCount: e.attendeeIds?.length ?? 0,
        isAttending: mockEventAttendees.has(e.id),
        myRsvpStatus: mockEventAttendees.get(e.id),
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
    if (pagination) {
      const offset = pagination.offset ?? 0;
      const limit = pagination.limit ?? all.length;
      return all.slice(offset, offset + limit);
    }
    return all;
  }

  async createEvent(input: CreateEventInput): Promise<CollectorsEvent> {
    const event: CollectorsEvent = {
      id: `event-mock-${Date.now()}`,
      title: input.title,
      kind: input.kind,
      date: input.date,
      time: input.time,
      endDate: input.endDate,
      location: input.location,
      onlineUrl: input.onlineUrl,
      description: input.description,
      categoryId: input.categoryId,
      hostUserId: 'collector-aurora',
      attendeeIds: ['collector-aurora'],
      attendeeCount: 1,
      isAttending: true,
      myRsvpStatus: 'going',
      source: 'user',
      createdBy: 'collector-aurora',
      format: input.format,
      isPublic: input.isPublic,
      latitude: input.latitude,
      longitude: input.longitude,
      // Sponsor fields
      ...(input.sponsorCompanyId ? {
        isSponsored: true,
        sponsorCompanyId: input.sponsorCompanyId,
        sponsorTier: input.sponsorTier ?? 'featured',
        sponsorName: this._sponsorCompanies.find((c) => c.id === input.sponsorCompanyId)?.name,
        sponsorLogoUrl: this._sponsorCompanies.find((c) => c.id === input.sponsorCompanyId)?.logoUrl,
      } : {}),
    };
    EVENTS.push(event);
    logger.info('[MockDataProvider] createEvent', { id: event.id, title: event.title });
    return event;
  }

  async rsvpEvent(eventId: string, status: string = 'going'): Promise<void> {
    mockEventAttendees.set(eventId, status);
    logger.info('[MockDataProvider] rsvpEvent', { eventId, status });
  }

  async unrsvpEvent(eventId: string): Promise<void> {
    mockEventAttendees.delete(eventId);
    logger.info('[MockDataProvider] unrsvpEvent', { eventId });
  }

  async shareEventViaDm(eventId: string, recipientUserId: string): Promise<void> {
    logger.info('[MockDataProvider] shareEventViaDm (no-op)', { eventId, recipientUserId });
  }

  async updateEvent(eventId: string, patch: Partial<CreateEventInput & { status?: string }>): Promise<CollectorsEvent> {
    const event = EVENTS.find((e) => e.id === eventId);
    if (!event) throw new Error(`Event not found: ${eventId}`);
    Object.assign(event, patch);
    logger.info('[MockDataProvider] updateEvent', { eventId });
    return event;
  }

  async cancelEvent(eventId: string): Promise<void> {
    const idx = EVENTS.findIndex((e) => e.id === eventId);
    if (idx >= 0) EVENTS.splice(idx, 1);
    logger.info('[MockDataProvider] cancelEvent', { eventId });
  }

  async duplicateEvent(eventId: string): Promise<CollectorsEvent> {
    const event = EVENTS.find((e) => e.id === eventId);
    if (!event) throw new Error(`Event not found: ${eventId}`);
    const dup: CollectorsEvent = { ...event, id: `event-dup-${Date.now()}`, title: `${event.title} (Copy)` };
    EVENTS.push(dup);
    return dup;
  }

  async listEventTemplates(): Promise<import('./events').EventTemplate[]> {
    return [];
  }

  async createEventTemplate(name: string, _fromEventId?: string): Promise<import('./events').EventTemplate> {
    return { id: `tpl-mock-${Date.now()}`, name, templateData: {}, useCount: 0 };
  }

  async deleteEventTemplate(_templateId: string): Promise<void> {}

  /** In-memory sponsor companies for demo flow */
  private _sponsorCompanies: import('./events').SponsorCompany[] = [
    {
      id: 'sponsor-demo-1',
      name: 'CollectAI Demo Sponsor',
      logoUrl: undefined,
      websiteUrl: 'https://ccollect.ai',
      contactEmail: 'sponsor@ccollect.ai',
      description: 'Demo sponsor company for testing the full dashboard experience. Edit this profile, create sponsored events, and explore all sponsor features.',
      adminUserId: 'collector-aurora',
      isVerified: true,
      createdAt: '2026-01-15T10:00:00Z',
    },
  ];

  async registerSponsorCompany(input: {
    name: string; logoUrl?: string; websiteUrl?: string;
    contactEmail: string; description?: string;
  }): Promise<import('./events').SponsorCompany> {
    const company: import('./events').SponsorCompany = {
      id: `sponsor-mock-${Date.now()}`,
      name: input.name,
      logoUrl: input.logoUrl,
      websiteUrl: input.websiteUrl,
      contactEmail: input.contactEmail,
      description: input.description,
      adminUserId: 'collector-aurora',
      isVerified: false,
    };
    this._sponsorCompanies.push(company);
    return company;
  }

  async getMySponsorCompanies(): Promise<import('./events').SponsorCompany[]> {
    return this._sponsorCompanies;
  }

  async updateSponsorCompany(id: string, patch: Partial<{
    name: string; logoUrl: string; websiteUrl: string;
    contactEmail: string; description: string;
  }>): Promise<import('./events').SponsorCompany> {
    const idx = this._sponsorCompanies.findIndex((c) => c.id === id);
    if (idx >= 0) {
      this._sponsorCompanies[idx] = { ...this._sponsorCompanies[idx], ...patch };
      return this._sponsorCompanies[idx];
    }
    return { id, name: patch.name ?? 'Mock Company', contactEmail: patch.contactEmail ?? 'mock@test.com', adminUserId: 'collector-aurora', isVerified: false };
  }

  async createSponsorEventCheckout(_companyId: string, _tier: string, _eventData: CreateEventInput): Promise<{ url: string; sessionId: string; eventId: string }> {
    // Demo bypass: skip Stripe, create event directly
    const eventId = `event-sponsor-${Date.now()}`;
    return { url: '', sessionId: 'cs_demo_bypass', eventId };
  }

  async listEventAnnouncements(_eventId: string): Promise<import('./events').EventAnnouncement[]> {
    return [];
  }

  async postEventAnnouncement(eventId: string, body: string, title?: string, imageUrl?: string): Promise<import('./events').EventAnnouncement> {
    return { id: `ann-mock-${Date.now()}`, eventId, authorUserId: 'collector-aurora', body, title, imageUrl, isRead: false };
  }

  async markAnnouncementRead(_eventId: string, _announcementId: string): Promise<void> {}

  async getUnreadAnnouncementCount(): Promise<number> {
    return 0;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Category Deep Dive Analytics
  // ─────────────────────────────────────────────────────────────────────────────

  async getCategoryDeepDive(_categoryId: string, _days?: number): Promise<Record<string, unknown>> {
    // Return empty mock data
    return {
      average_market_price: 0,
      value_distribution: {},
      top_traded_items: [],
      top_movers: [],
    };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // User Search
  // ─────────────────────────────────────────────────────────────────────────────

  async searchUsers(query: string): Promise<PublicUserProfile[]> {
    if (!query.trim()) return [];

    const lowerQuery = query.toLowerCase();

    // All mock profiles to search against
    const allProfiles: PublicUserProfile[] = [
      {
        id: 'collector-aurora',
        displayName: 'Aurora',
        handle: 'aurora.cards',
        avatarUrl: null,
        bio: 'Modern + vintage Pokemon with a side of Disney Lorcana.',
        interests: ['Pokemon Cards', 'Disney Lorcana', 'Funko Pops'],
        collectionCount: 186,
        collectionValueEur: 12450,
      },
      {
        id: 'collector-rune',
        displayName: 'Rune',
        handle: 'rune.mtgguy',
        avatarUrl: null,
        bio: 'MTG reserve list and Flesh and Blood legendaries.',
        interests: ['Magic: The Gathering', 'Flesh and Blood'],
        collectionCount: 210,
        collectionValueEur: 18400,
      },
      {
        id: 'collector-mini',
        displayName: 'Mini Martian',
        handle: 'mini.martian',
        avatarUrl: null,
        bio: 'Warhammer and Gunpla painter.',
        interests: ['Warhammer Minis', 'Gunpla & Model Kits'],
        collectionCount: 95,
        collectionValueEur: 6200,
      },
      {
        id: 'collector-alex',
        displayName: 'Alex TCG',
        handle: 'alex.tcg',
        avatarUrl: null,
        bio: 'Trading card games enthusiast.',
        interests: ['Pokemon Cards', 'Magic: The Gathering'],
        collectionCount: 340,
        collectionValueEur: 22000,
      },
      {
        id: 'collector-kai',
        displayName: 'Kai Bricks',
        handle: 'kai.bricks',
        avatarUrl: null,
        bio: 'LEGO builder and collector.',
        interests: ['LEGO', 'Hot Wheels'],
        collectionCount: 120,
        collectionValueEur: 8900,
      },
    ];

    return allProfiles.filter(
      (p) =>
        p.displayName.toLowerCase().includes(lowerQuery) ||
        (p.handle && p.handle.toLowerCase().includes(lowerQuery))
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // User Blocking
  // ─────────────────────────────────────────────────────────────────────────────

  async blockUser(userId: string): Promise<void> {
    mockBlockedUsers.add(userId);
    // Auto-decline pending DM requests from this user
    for (const [threadId, req] of mockDmRequests.entries()) {
      if (req.fromUserId === userId) {
        mockDmRequests.delete(threadId);
        mockDmStatusByUser.set(userId, 'declined');
      }
    }
    logger.info('[MockDataProvider] blockUser', { userId });
  }

  async unblockUser(userId: string): Promise<void> {
    mockBlockedUsers.delete(userId);
    logger.info('[MockDataProvider] unblockUser', { userId });
  }

  async listBlockedUsers(): Promise<{ id: string; name: string }[]> {
    const results: { id: string; name: string }[] = [];
    for (const userId of mockBlockedUsers) {
      const profile = await this.getPublicUserProfile(userId);
      results.push({ id: userId, name: profile?.displayName ?? 'Unknown' });
    }
    return results;
  }

  async isBlocked(userId: string): Promise<boolean> {
    return mockBlockedUsers.has(userId);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Barcode / Market Data
  // ─────────────────────────────────────────────────────────────────────────────

  async lookupByBarcode(
    barcode: string,
    opts?: { codeType?: string },
  ): Promise<BarcodeLookupResult> {
    logger.info('[MockDataProvider] lookupByBarcode', { barcode, opts });

    // Mock fixtures for known barcodes
    const fixtures: Record<string, BarcodeLookupResult> = {
      // Warhammer 40K Rulebook ISBN
      '9781839063077': {
        title: 'Warhammer 40,000: Core Book (10th Edition)',
        categoryId: 'warhammer',
        subtypeId: 'rulebook',
        taxonomyVersion: 'v1.0',
        collections: [],
        attributes: {
          publisher: 'Games Workshop',
          isbn: '9781839063077',
          format: 'Hardcover',
          pages: 280,
        },
        missingRequired: [],
        priceBand: {
          q10: 45,
          q50: 55,
          q90: 65,
          confidence: 0.85,
          currency: 'EUR',
        },
        rationale: ['Matched ISBN to Games Workshop product catalog', 'Price from recent eBay sold comps'],
        barcode,
        barcodeType: opts?.codeType || 'isbn',
        imageUrl: null,
      },

      // BTS - Proof Album (Standard Edition) - real barcode
      '8809848755491': {
        title: 'BTS - Proof (Standard Edition)',
        categoryId: 'music_media',
        subtypeId: 'album',
        taxonomyVersion: 'v1.0',
        collections: ['bts'],
        attributes: {
          artist: 'BTS',
          album: 'Proof',
          edition: 'Standard',
          format: 'CD Box Set',
          releaseYear: 2022,
          label: 'BigHit Entertainment',
        },
        missingRequired: [],
        priceBand: {
          q10: 35,
          q50: 55,
          q90: 85,
          confidence: 0.82,
          currency: 'EUR',
        },
        rationale: ['Matched to BTS anthology album', 'Collection tag: bts', 'Price from Discogs/eBay sold'],
        barcode,
        barcodeType: opts?.codeType || 'ean13',
        imageUrl: null,
      },

      // BTS - Map of the Soul: 7 - another fixture
      '8809440339068': {
        title: 'BTS - Map of the Soul: 7',
        categoryId: 'music_media',
        subtypeId: 'album',
        taxonomyVersion: 'v1.0',
        collections: ['bts'],
        attributes: {
          artist: 'BTS',
          album: 'Map of the Soul: 7',
          format: 'CD',
          releaseYear: 2020,
          label: 'BigHit Entertainment',
        },
        missingRequired: [],
        priceBand: {
          q10: 20,
          q50: 35,
          q90: 60,
          confidence: 0.88,
          currency: 'EUR',
        },
        rationale: ['K-pop album matched via barcode', 'Collection tag: bts'],
        barcode,
        barcodeType: opts?.codeType || 'ean13',
        imageUrl: null,
      },

      // Taylor Swift - Eras Tour merch (example UPC)
      '843930092451': {
        title: 'Taylor Swift Eras Tour Crewneck Sweater (Black, L)',
        categoryId: 'music_media',
        subtypeId: 'tour_merch',
        taxonomyVersion: 'v1.0',
        collections: ['taylor_swift', 'eras_tour'],
        attributes: {
          artist: 'Taylor Swift',
          tour: 'Eras Tour',
          itemType: 'Apparel',
          size: 'L',
          color: 'Black',
          year: 2023,
        },
        missingRequired: [],
        priceBand: {
          q10: 85,
          q50: 120,
          q90: 175,
          confidence: 0.75,
          currency: 'EUR',
        },
        rationale: ['Tour merch matched via UPC', 'Collections: taylor_swift, eras_tour', 'High demand item'],
        barcode,
        barcodeType: opts?.codeType || 'upc_a',
        imageUrl: null,
      },

      // Taylor Swift - 1989 (Taylor's Version) vinyl
      '602455542472': {
        title: 'Taylor Swift - 1989 (Taylor\'s Version) Vinyl LP',
        categoryId: 'music_media',
        subtypeId: 'vinyl',
        taxonomyVersion: 'v1.0',
        collections: ['taylor_swift'],
        attributes: {
          artist: 'Taylor Swift',
          album: '1989 (Taylor\'s Version)',
          format: 'Vinyl LP',
          releaseYear: 2023,
          label: 'Republic Records',
        },
        missingRequired: [],
        priceBand: {
          q10: 30,
          q50: 40,
          q90: 55,
          confidence: 0.9,
          currency: 'EUR',
        },
        rationale: ['Vinyl album matched via UPC', 'Collection tag: taylor_swift'],
        barcode,
        barcodeType: opts?.codeType || 'upc_a',
        imageUrl: null,
      },

      // Generic book ISBN for testing
      '9780593499597': {
        title: 'Fourth Wing (Hardcover)',
        categoryId: 'books',
        subtypeId: 'fiction',
        taxonomyVersion: 'v1.0',
        collections: [],
        attributes: {
          author: 'Rebecca Yarros',
          publisher: 'Red Tower Books',
          isbn: '9780593499597',
          format: 'Hardcover',
        },
        missingRequired: [],
        priceBand: {
          q10: 18,
          q50: 25,
          q90: 32,
          confidence: 0.92,
          currency: 'EUR',
        },
        rationale: ['ISBN matched via Open Library / Google Books'],
        barcode,
        barcodeType: opts?.codeType || 'isbn',
        imageUrl: null,
      },
    };

    // Check if we have a fixture for this barcode
    if (fixtures[barcode]) {
      // Simulate network delay
      await new Promise((r) => setTimeout(r, 500));
      return fixtures[barcode];
    }

    // Unknown barcode - return minimal result with missing fields
    await new Promise((r) => setTimeout(r, 300));
    return {
      title: null,
      categoryId: null,
      subtypeId: null,
      taxonomyVersion: 'v1.0',
      collections: [],
      attributes: {},
      missingRequired: ['title', 'categoryId'],
      priceBand: null,
      rationale: ['Barcode not found in product databases', 'Try manual search with keywords'],
      barcode,
      barcodeType: opts?.codeType || 'unknown',
      imageUrl: null,
    };
  }

  async marketSearch(
    query: string,
    opts?: MarketSearchOptions,
  ): Promise<MarketSearchResult> {
    logger.info('[MockDataProvider] marketSearch', { query, opts });

    // Simulate network delay
    await new Promise((r) => setTimeout(r, 400));

    // Generate mock hits based on query
    const mockHits: MarketHit[] = [];
    const lowerQuery = query.toLowerCase();

    // BTS-related searches
    if (lowerQuery.includes('bts') || opts?.collections?.includes('bts')) {
      mockHits.push(
        {
          source: 'ebay',
          rawId: 'ebay-bts-001',
          title: 'BTS Proof Album Standard Edition Sealed',
          price: 52,
          currency: 'EUR',
          soldAt: '2026-01-28T14:30:00Z',
          url: 'https://ebay.com/itm/bts-proof-001',
          condition: 'New',
          imageUrl: null,
          rawPayloadHash: 'abc123',
        },
        {
          source: 'discogs',
          rawId: 'discogs-bts-002',
          title: 'BTS - Map of the Soul: 7 CD Box',
          price: 38,
          currency: 'EUR',
          soldAt: '2026-01-25T10:00:00Z',
          url: 'https://discogs.com/sell/item/bts-mots7',
          condition: 'Mint',
          imageUrl: null,
          rawPayloadHash: 'def456',
        },
      );
    }

    // Taylor Swift-related searches
    if (lowerQuery.includes('taylor') || lowerQuery.includes('swift') || opts?.collections?.includes('taylor_swift')) {
      mockHits.push(
        {
          source: 'ebay',
          rawId: 'ebay-ts-001',
          title: 'Taylor Swift Eras Tour Crewneck Black Large',
          price: 115,
          currency: 'EUR',
          soldAt: '2026-01-30T16:45:00Z',
          url: 'https://ebay.com/itm/ts-eras-001',
          condition: 'New with tags',
          imageUrl: null,
          rawPayloadHash: 'ghi789',
        },
        {
          source: 'ebay',
          rawId: 'ebay-ts-002',
          title: 'Taylor Swift 1989 TV Vinyl LP Sealed',
          price: 42,
          currency: 'EUR',
          soldAt: '2026-01-29T12:00:00Z',
          url: 'https://ebay.com/itm/ts-1989-001',
          condition: 'New',
          imageUrl: null,
          rawPayloadHash: 'jkl012',
        },
      );
    }

    // Warhammer-related searches
    if (lowerQuery.includes('warhammer') || lowerQuery.includes('40k') || opts?.categoryId === 'warhammer') {
      mockHits.push(
        {
          source: 'ebay',
          rawId: 'ebay-wh-001',
          title: 'Warhammer 40K Core Book 10th Edition',
          price: 52,
          currency: 'EUR',
          soldAt: '2026-01-27T09:15:00Z',
          url: 'https://ebay.com/itm/wh40k-core',
          condition: 'Like New',
          imageUrl: null,
          rawPayloadHash: 'mno345',
        },
      );
    }

    // Generic fallback hits if query doesn't match specific collections
    if (mockHits.length === 0 && query.length > 2) {
      mockHits.push(
        {
          source: 'ebay',
          rawId: `ebay-generic-${Date.now()}`,
          title: `${query} - Similar Item Found`,
          price: Math.floor(Math.random() * 100) + 20,
          currency: 'EUR',
          soldAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
          url: null,
          condition: 'Used',
          imageUrl: null,
          rawPayloadHash: `generic-${Date.now()}`,
        },
      );
    }

    // Apply filters
    let filteredHits = mockHits;
    if (opts?.soldOnly) {
      filteredHits = filteredHits.filter((h) => h.soldAt);
    }
    if (opts?.minPrice !== undefined) {
      filteredHits = filteredHits.filter((h) => h.price >= opts.minPrice!);
    }
    if (opts?.maxPrice !== undefined) {
      filteredHits = filteredHits.filter((h) => h.price <= opts.maxPrice!);
    }
    if (opts?.limit) {
      filteredHits = filteredHits.slice(0, opts.limit);
    }

    return {
      hits: filteredHits,
      providers: ['ebay', 'discogs'],
      totalRaw: mockHits.length,
      confidence: mockHits.length > 0 ? 0.8 : 0.2,
    };
  }
  // ─── Presence ───────────────────────────────────────────────────────────────

  async sendHeartbeat(): Promise<void> { /* no-op */ }
  async goOffline(): Promise<void> { /* no-op */ }

  async getUserPresence(userId: string): Promise<import('./types').UserPresence | null> {
    return { userId, lastSeenAt: new Date().toISOString(), isOnline: true };
  }

  async getBatchPresence(userIds: string[]): Promise<import('./types').UserPresence[]> {
    return userIds.map((userId) => ({ userId, lastSeenAt: new Date().toISOString(), isOnline: true }));
  }

  // ─── Activity Feed ─────────────────────────────────────────────────────────

  async getUserActivity(userId: string, limit = 20, offset = 0): Promise<import('./types').ActivityFeedItem[]> {
    return [
      { id: '1', userId, activityType: 'item_added' as const, title: 'Added Charizard Base Set', description: null, metadata: {}, isPublic: true, createdAt: new Date().toISOString() },
      { id: '2', userId, activityType: 'event_rsvp' as const, title: "RSVP'd to Pokemon TCG Night", description: null, metadata: {}, isPublic: true, createdAt: new Date(Date.now() - 86400000).toISOString() },
      { id: '3', userId, activityType: 'achievement_earned' as const, title: 'Earned "Collector" badge', description: 'Reached 10 items', metadata: {}, isPublic: true, createdAt: new Date(Date.now() - 172800000).toISOString() },
    ].slice(offset, offset + limit);
  }

  async logActivity(_activityType: string, _title: string, _description?: string, _metadata?: Record<string, unknown>, _isPublic?: boolean): Promise<void> { /* no-op */ }

  // ─── Unified Search ────────────────────────────────────────────────────────

  async unifiedSearch(query: string, limit = 5) {
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

  // ─── Event Search ──────────────────────────────────────────────────────────

  async searchEvents(params: {
    q?: string;
    category?: string;
    eventType?: string;
    location?: string;
    upcomingOnly?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<import('./events').CollectorsEvent[]> {
    let results = [...EVENTS];
    if (params.q) {
      const q = params.q.toLowerCase();
      results = results.filter((e) => e.title.toLowerCase().includes(q) || (e.description || '').toLowerCase().includes(q));
    }
    if (params.category) {
      results = results.filter((e) => e.categoryId === params.category);
    }
    return results.slice(params.offset || 0, (params.offset || 0) + (params.limit || 20));
  }

  // ─── Deal Desk (P2P Offers) ───────────────────────────────────────────────

  async proposeOffer(itemId: string, price: number, message?: string): Promise<Offer> {
    const now = new Date().toISOString();
    return {
      id: `offer-${Date.now()}`,
      itemId,
      itemTitle: 'Mock Item',
      itemImageUrl: null,
      sellerId: 'seller-mock',
      buyerId: 'buyer-mock',
      status: 'proposed',
      currentPrice: price,
      currency: 'EUR',
      otherUserId: 'seller-mock',
      otherUserName: 'MockSeller',
      otherUserAvatarUrl: null,
      dmThreadId: `thread-${Date.now()}`,
      createdAt: now,
      updatedAt: now,
      expiresAt: null,
    };
  }

  async counterOffer(offerId: string, price: number, message?: string): Promise<Offer> {
    const now = new Date().toISOString();
    return {
      id: offerId,
      itemId: 'item-mock',
      itemTitle: 'Mock Item',
      itemImageUrl: null,
      sellerId: 'seller-mock',
      buyerId: 'buyer-mock',
      status: 'countered',
      currentPrice: price,
      currency: 'EUR',
      otherUserId: 'buyer-mock',
      otherUserName: 'MockBuyer',
      otherUserAvatarUrl: null,
      dmThreadId: `thread-${Date.now()}`,
      createdAt: now,
      updatedAt: now,
      expiresAt: null,
    };
  }

  async respondToOffer(_offerId: string, _accept: boolean, _message?: string): Promise<void> {
    /* no-op */
  }

  async cancelOffer(_offerId: string): Promise<void> {
    /* no-op */
  }

  async listActiveOffers(): Promise<Offer[]> {
    return [];
  }

  async listDealHistory(): Promise<Offer[]> {
    return [];
  }

  async getOfferDetail(offerId: string): Promise<{ offer: Offer; events: OfferEvent[] }> {
    const now = new Date().toISOString();
    return {
      offer: {
        id: offerId,
        itemId: 'item-mock',
        itemTitle: 'Mock Item',
        itemImageUrl: null,
        sellerId: 'seller-mock',
        buyerId: 'buyer-mock',
        status: 'proposed',
        currentPrice: 100,
        currency: 'EUR',
        otherUserId: 'seller-mock',
        otherUserName: 'MockSeller',
        otherUserAvatarUrl: null,
        dmThreadId: `thread-mock`,
        createdAt: now,
        updatedAt: now,
        expiresAt: null,
      },
      events: [],
    };
  }

  async getUserReputation(userId: string): Promise<UserReputation> {
    return {
      userId,
      avgStars: 4.5,
      totalRatings: 0,
      completedDeals: 0,
    };
  }

  async toggleForSale(_itemId: string, _forSale: boolean, _askingPrice?: number): Promise<void> {
    /* no-op */
  }

  async markShipped(_offerId: string, _trackingInfo?: string): Promise<void> {
    /* no-op */
  }

  async completeDeal(_offerId: string, _stars: number, _comment?: string): Promise<void> {
    /* no-op */
  }

  // Multi-Marketplace Selling — seeded mock data
  private _mockListings: import('./types').MarketplaceListing[] = [
    { id: 'ml-1', itemId: 'item-1', marketplaceId: 'ebay', listingTitle: 'PSA 10 Charizard Base Set Holo 1st Edition', price: 12500, currency: 'EUR', format: 'auction', quantity: 1, status: 'active', viewsCount: 342, watchersCount: 28, offersCount: 3, estimatedFees: 1612, estimatedNet: 10888, feePercentage: 12.9, listedAt: '2026-02-20T10:00:00Z', syncedAt: '2026-02-27T08:00:00Z', createdAt: '2026-02-20T10:00:00Z' },
    { id: 'ml-2', itemId: 'item-2', marketplaceId: 'collectai', listingTitle: 'LEGO Star Wars UCS AT-AT 75313 (Sealed)', price: 899, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'active', viewsCount: 56, watchersCount: 8, offersCount: 1, estimatedFees: 0, estimatedNet: 899, feePercentage: 0, listedAt: '2026-02-22T14:30:00Z', syncedAt: '2026-02-27T08:00:00Z', createdAt: '2026-02-22T14:30:00Z' },
    { id: 'ml-3', itemId: 'item-3', marketplaceId: 'cardmarket', listingTitle: 'MTG Black Lotus Beta (HP)', price: 18000, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'draft', viewsCount: 0, watchersCount: 0, offersCount: 0, createdAt: '2026-02-25T09:00:00Z' },
    { id: 'ml-4', itemId: 'item-4', marketplaceId: 'mercari', listingTitle: 'Warhammer 40K Leviathan Box Set (NOS)', price: 180, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'sold', viewsCount: 124, watchersCount: 15, offersCount: 2, soldAt: '2026-02-24T16:45:00Z', syncedAt: '2026-02-25T08:00:00Z', createdAt: '2026-02-18T11:00:00Z' },
    { id: 'ml-5', itemId: 'item-5', marketplaceId: 'ebay', listingTitle: 'Funko Pop Freddy Funko as Batman SDCC 2019', price: 320, currency: 'EUR', format: 'best_offer', quantity: 1, status: 'delisted', viewsCount: 89, watchersCount: 6, offersCount: 0, statusMessage: 'Relisted on CollectAI P2P', createdAt: '2026-02-10T08:00:00Z' },
  ];

  private _mockSales: import('./types').MarketplaceSale[] = [
    { id: 'ms-1', listingId: 'ml-4', buyerName: 'collector_jane', salePrice: 180, currency: 'EUR', shippingCostActual: 8.50, platformFee: 18, paymentProcessingFee: 0, netProceeds: 153.50, status: 'completed', soldAt: '2026-02-24T16:45:00Z' },
    { id: 'ms-2', listingId: 'ml-old-1', buyerName: 'pokefan_2026', salePrice: 450, currency: 'EUR', shippingCostActual: 12, platformFee: 58.05, paymentProcessingFee: 13.35, netProceeds: 366.60, trackingNumber: 'DHL-1234567890', carrier: 'DHL', status: 'completed', soldAt: '2026-02-15T12:00:00Z' },
    { id: 'ms-3', listingId: 'ml-old-2', buyerName: null, salePrice: 95, currency: 'EUR', platformFee: 0, paymentProcessingFee: 0, netProceeds: 95, status: 'shipped', soldAt: '2026-02-26T09:30:00Z' },
  ];

  private _mockAccounts: import('./types').MarketplaceAccount[] = [
    { id: 'ma-1', marketplaceId: 'ebay', sellerName: 'CollectAI_Pro', isActive: true, connectedAt: '2025-11-01T10:00:00Z', lastSyncAt: '2026-02-27T08:00:00Z' },
    { id: 'ma-2', marketplaceId: 'collectai', sellerName: 'demo_seller', isActive: true, connectedAt: '2026-01-15T14:00:00Z', lastSyncAt: '2026-02-27T08:00:00Z' },
  ];

  async listMarketplaceListings(): Promise<import('./types').MarketplaceListing[]> { return this._mockListings; }
  async createMarketplaceListing(input: Omit<import('./types').MarketplaceListing, 'id' | 'viewsCount' | 'watchersCount' | 'offersCount' | 'createdAt'>): Promise<import('./types').MarketplaceListing> {
    const listing = { ...input, id: `mock-listing-${Date.now()}`, viewsCount: 0, watchersCount: 0, offersCount: 0, createdAt: new Date().toISOString() } as import('./types').MarketplaceListing;
    this._mockListings.unshift(listing);
    return listing;
  }
  async updateMarketplaceListing(_listingId: string, _patch: Partial<import('./types').MarketplaceListing>): Promise<import('./types').MarketplaceListing> { throw new Error('Not implemented'); }
  async deleteMarketplaceListing(listingId: string): Promise<void> { this._mockListings = this._mockListings.filter((l) => l.id !== listingId); }
  async listMarketplaceAccounts(): Promise<import('./types').MarketplaceAccount[]> { return this._mockAccounts; }
  async listMarketplaceSales(): Promise<import('./types').MarketplaceSale[]> { return this._mockSales; }
  async getMarketplaceFeeSchedules(): Promise<import('./types').MarketplaceFeeSchedule[]> {
    return [
      { marketplaceId: 'collectai', displayName: 'CollectAI P2P', baseFeePct: 0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: 'Free P2P trading' },
      { marketplaceId: 'ebay', displayName: 'eBay', baseFeePct: 12.9, paymentProcessingPct: 2.9, fixedFee: 0.30, currency: 'EUR', notes: 'Final value fee + payment processing' },
      { marketplaceId: 'mercari', displayName: 'Mercari', baseFeePct: 10.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: 'Flat 10% seller fee' },
      { marketplaceId: 'cardmarket', displayName: 'Cardmarket', baseFeePct: 5.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: '5% commission' },
      { marketplaceId: 'stockx', displayName: 'StockX', baseFeePct: 9.5, paymentProcessingPct: 3.0, fixedFee: 0, currency: 'EUR', notes: 'Transaction + payment processing' },
      { marketplaceId: 'bricklink', displayName: 'BrickLink', baseFeePct: 3.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: '3% final value fee' },
    ];
  }
}

// Singleton instance
export const mockDataProvider = new MockDataProvider();
