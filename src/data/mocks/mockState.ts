/**
 * Shared in-memory state for mock data provider modules.
 * All mock domain modules read/write from these stores so state is consistent.
 */

import type {
  Item,
  WatchlistItem,
  DmThread,
  DmRequest,
  DmMessage,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
} from '../types';
import type { SponsorCompany } from '../events';

// ─── Items ──────────────────────────────────────────────────────────────────
export let mockCreatedItems: Item[] = [];
export function setMockCreatedItems(items: Item[]): void {
  mockCreatedItems = items;
}

// ─── Watchlist ──────────────────────────────────────────────────────────────
export let mockWatchlistItems: WatchlistItem[] = [
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
export function setMockWatchlistItems(items: WatchlistItem[]): void {
  mockWatchlistItems = items;
}

// ─── Categories ─────────────────────────────────────────────────────────────
export const mockFollowedCategories: Set<string> = new Set(['pokemon', 'warhammer', 'lego']);
export const ownedCategoryItems: Set<string> = new Set();

// ─── Events ─────────────────────────────────────────────────────────────────
export const mockEventAttendees: Map<string, string> = new Map();

// ─── Chat / DM ──────────────────────────────────────────────────────────────
export const mockDmThreads: Map<string, DmThread> = new Map([
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

export const mockDmRequests: Map<string, DmRequest> = new Map([
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

export const mockDmMessages: Map<string, DmMessage[]> = new Map([
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

export const mockBlockedUsers: Set<string> = new Set();

export const mockDmStatusByUser: Map<string, 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> = new Map([
  ['collector-rune', 'accepted'],
  ['collector-mini', 'accepted'],
  ['collector-alex', 'pending_incoming'],
]);

// ─── Build & Paint ──────────────────────────────────────────────────────────
export const mockBuildPaintProjects: Map<string, BuildPaintProject> = new Map([
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

export const mockBuildPaintSteps: Map<string, BuildPaintStep[]> = new Map([
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

export const mockBuildPaintNotes: Map<string, BuildPaintNote[]> = new Map([
  ['bp-mock-1', [
    { id: 'note-1-1', projectId: 'bp-mock-1', body: 'Decided on urban camo pattern - grey base with dark grey camo stripes', createdAt: '2025-12-01T11:00:00Z' },
    { id: 'note-1-2', projectId: 'bp-mock-1', body: 'Zenithal prime worked great. Using Vallejo German Grey as base.', createdAt: '2025-12-03T14:00:00Z' },
  ]],
  ['bp-mock-2', [
    { id: 'note-2-1', projectId: 'bp-mock-2', body: 'Using Tamiya Panel Line Accent - brown for white parts, black for dark parts', createdAt: '2025-11-26T10:00:00Z' },
  ]],
]);

// ─── Sponsor Companies ─────────────────────────────────────────────────────
export const mockSponsorCompanies: SponsorCompany[] = [
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

// ─── Multi-Marketplace Selling ──────────────────────────────────────────────
export let mockListings: import('../types').MarketplaceListing[] = [
  { id: 'ml-1', itemId: 'item-1', marketplaceId: 'ebay', listingTitle: 'PSA 10 Charizard Base Set Holo 1st Edition', price: 12500, currency: 'EUR', format: 'auction', quantity: 1, status: 'active', viewsCount: 342, watchersCount: 28, offersCount: 3, estimatedFees: 1612, estimatedNet: 10888, feePercentage: 12.9, listedAt: '2026-02-20T10:00:00Z', syncedAt: '2026-02-27T08:00:00Z', createdAt: '2026-02-20T10:00:00Z' },
  { id: 'ml-2', itemId: 'item-2', marketplaceId: 'collectai', listingTitle: 'LEGO Star Wars UCS AT-AT 75313 (Sealed)', price: 899, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'active', viewsCount: 56, watchersCount: 8, offersCount: 1, estimatedFees: 0, estimatedNet: 899, feePercentage: 0, listedAt: '2026-02-22T14:30:00Z', syncedAt: '2026-02-27T08:00:00Z', createdAt: '2026-02-22T14:30:00Z' },
  { id: 'ml-3', itemId: 'item-3', marketplaceId: 'cardmarket', listingTitle: 'MTG Black Lotus Beta (HP)', price: 18000, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'draft', viewsCount: 0, watchersCount: 0, offersCount: 0, createdAt: '2026-02-25T09:00:00Z' },
  { id: 'ml-4', itemId: 'item-4', marketplaceId: 'mercari', listingTitle: 'Warhammer 40K Leviathan Box Set (NOS)', price: 180, currency: 'EUR', format: 'fixed_price', quantity: 1, status: 'sold', viewsCount: 124, watchersCount: 15, offersCount: 2, soldAt: '2026-02-24T16:45:00Z', syncedAt: '2026-02-25T08:00:00Z', createdAt: '2026-02-18T11:00:00Z' },
  { id: 'ml-5', itemId: 'item-5', marketplaceId: 'ebay', listingTitle: 'Funko Pop Freddy Funko as Batman SDCC 2019', price: 320, currency: 'EUR', format: 'best_offer', quantity: 1, status: 'delisted', viewsCount: 89, watchersCount: 6, offersCount: 0, statusMessage: 'Relisted on CollectAI P2P', createdAt: '2026-02-10T08:00:00Z' },
];
export function setMockListings(listings: import('../types').MarketplaceListing[]): void {
  mockListings = listings;
}

export const mockSales: import('../types').MarketplaceSale[] = [
  { id: 'ms-1', listingId: 'ml-4', buyerName: 'collector_jane', salePrice: 180, currency: 'EUR', shippingCostActual: 8.50, platformFee: 18, paymentProcessingFee: 0, netProceeds: 153.50, status: 'completed', soldAt: '2026-02-24T16:45:00Z' },
  { id: 'ms-2', listingId: 'ml-old-1', buyerName: 'pokefan_2026', salePrice: 450, currency: 'EUR', shippingCostActual: 12, platformFee: 58.05, paymentProcessingFee: 13.35, netProceeds: 366.60, trackingNumber: 'DHL-1234567890', carrier: 'DHL', status: 'completed', soldAt: '2026-02-15T12:00:00Z' },
  { id: 'ms-3', listingId: 'ml-old-2', buyerName: null, salePrice: 95, currency: 'EUR', platformFee: 0, paymentProcessingFee: 0, netProceeds: 95, status: 'shipped', soldAt: '2026-02-26T09:30:00Z' },
];

export const mockAccounts: import('../types').MarketplaceAccount[] = [
  { id: 'ma-1', marketplaceId: 'ebay', sellerName: 'CollectAI_Pro', isActive: true, connectedAt: '2025-11-01T10:00:00Z', lastSyncAt: '2026-02-27T08:00:00Z' },
  { id: 'ma-2', marketplaceId: 'collectai', sellerName: 'demo_seller', isActive: true, connectedAt: '2026-01-15T14:00:00Z', lastSyncAt: '2026-02-27T08:00:00Z' },
];
