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
} from './types';
import { getCategoryById, CATEGORIES, type Category } from './categories';
import { EVENTS, type CollectorsEvent } from './events';
import {
  MOCK_ANALYTICS_SUMMARY,
  MOCK_TOP_MOVERS,
  MOCK_TWITCH_CREATORS,
} from '../mockData';

// In-memory store for created items (persists only during session)
let mockCreatedItems: Item[] = [];

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
    title: 'LEGO UCS Millennium Falcon',
    priority: 'medium',
    owned: false,
    targetPrice: 700,
    currency: 'EUR',
    category: 'LEGO',
    notes: 'Birthday gift idea',
    createdAt: '2025-12-08T15:30:00Z',
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
    console.log('[MockDataProvider] addWatchlistItem', { id: newItem.id, title: newItem.title });
    return newItem;
  }

  async removeWatchlistItem(id: string): Promise<void> {
    const index = mockWatchlistItems.findIndex((item) => item.id === id);
    if (index !== -1) {
      mockWatchlistItems.splice(index, 1);
      console.log('[MockDataProvider] removeWatchlistItem', { id });
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

    console.log('[MockDataProvider] persistQuickscanDraft', { id, title, categoryId });

    return {
      id,
      title,
      categoryId,
      createdAt,
      imageUrl: input.photoUri,
    };
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
      // Vary completion for visual interest
      const totalCount = 50 + idx * 15;
      const ownedCount = Math.floor(totalCount * (0.3 + idx * 0.08));
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
    if (mockMissingItems[categoryId]) {
      return mockMissingItems[categoryId];
    }

    // Generic missing items for categories without specific mock data
    return Array.from({ length: 8 }, (_, i) => ({
      id: `${categoryId}-missing-${i + 1}`,
      categoryId,
      title: `${category.name} Item #${i + 1}`,
      brand: category.name,
      notes: i % 2 === 0 ? 'Rare variant' : null,
    }));
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Alerts Feed (read-only)
  // ─────────────────────────────────────────────────────────────────────────────

  async listAlertsFeed(): Promise<AlertFeedItem[]> {
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

    return mockAlerts;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // DM / Inbox methods
  // ─────────────────────────────────────────────────────────────────────────────

  async listInboxThreads(): Promise<DmThread[]> {
    // Return accepted threads sorted by last message
    const threads = Array.from(mockDmThreads.values())
      .filter((t) => t.status === 'accepted')
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

    console.log('[MockDataProvider] requestDm', { threadId, toUserId, message });
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

    console.log('[MockDataProvider] decideDmRequest', { threadId, accept });
  }

  async markThreadRead(threadId: string): Promise<void> {
    const thread = mockDmThreads.get(threadId);
    if (thread) {
      thread.unreadCount = 0;
      mockDmThreads.set(threadId, thread);
    }
    console.log('[MockDataProvider] markThreadRead', { threadId });
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

    console.log('[MockDataProvider] sendMessage', { threadId, body, messageId: newMessage.id });
    return newMessage;
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
    console.log('[MockDataProvider] createBuildPaintProject', { id, title: input.title });
    return project;
  }

  async setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
    const project = mockBuildPaintProjects.get(projectId);
    if (!project) return;

    project.percent = Math.max(0, Math.min(100, percent));
    if (status) project.status = status;
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
    console.log('[MockDataProvider] setBuildPaintProgress', { projectId, percent, status });
  }

  async markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
    const project = mockBuildPaintProjects.get(projectId);
    if (!project) return;

    project.isCompleted = isCompleted;
    project.status = isCompleted ? 'completed' : 'active';
    if (isCompleted) project.percent = 100;
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
    console.log('[MockDataProvider] markBuildPaintProjectComplete', { projectId, isCompleted });
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
    console.log('[MockDataProvider] addBuildPaintStep', { projectId, title, stepId: step.id });
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
        console.log('[MockDataProvider] toggleBuildPaintStep', { stepId, isDone });
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
    console.log('[MockDataProvider] addBuildPaintNote', { projectId, noteId: note.id });
    return note;
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
    console.log('[MockDataProvider] submitFeedback', { itemId, feedbackType, value, feedbackId });
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
    console.log('[MockDataProvider] submitCorrection', { itemId, corrections });
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
    console.log('[MockDataProvider] markCategoryItemOwned', { categoryItemId, quantity, notes });
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

    console.log('[MockDataProvider] convertWatchlistToItem', {
      watchlistItemId,
      actualPrice,
      notes,
      newItemId: newItem.id,
    });

    return newItem;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────────

  async getEventById(eventId: string): Promise<CollectorsEvent | null> {
    const event = EVENTS.find((e) => e.id === eventId);
    return event ?? null;
  }

  async listEvents(): Promise<CollectorsEvent[]> {
    // Return all events sorted by date (ascending)
    return [...EVENTS].sort((a, b) => a.date.localeCompare(b.date));
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Barcode / Market Data
  // ─────────────────────────────────────────────────────────────────────────────

  async lookupByBarcode(
    barcode: string,
    opts?: { codeType?: string },
  ): Promise<BarcodeLookupResult> {
    console.log('[MockDataProvider] lookupByBarcode', { barcode, opts });

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
    console.log('[MockDataProvider] marketSearch', { query, opts });

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
}

// Singleton instance
export const mockDataProvider = new MockDataProvider();
