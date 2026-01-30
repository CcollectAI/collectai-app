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
  DmThread,
  DmRequest,
  DmMessage,
  AnalyticsMetrics,
} from './types';
import { getCategoryById, type Category } from './categories';
import { EVENTS } from './events';
import {
  MOCK_ANALYTICS_SUMMARY,
  MOCK_TOP_MOVERS,
  MOCK_TWITCH_CREATORS,
} from '../mockData';

// In-memory store for created items (persists only during session)
let mockCreatedItems: Item[] = [];

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
    // Deterministic mock data for build & paint projects
    const activeProjects = 2;
    const backlogProjects = 5;
    const completedProjects = 8;
    const totalBuildMinutes = 1260; // ~21 hours
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
}

// Singleton instance
export const mockDataProvider = new MockDataProvider();
