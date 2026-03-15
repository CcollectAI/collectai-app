/**
 * Mock deals (P2P offers) + multi-marketplace selling domain provider.
 */

import type {
  Offer,
  OfferEvent,
  UserReputation,
  MarketplaceListing,
  MarketplaceAccount,
  MarketplaceSale,
  MarketplaceFeeSchedule,
} from '../types';
import {
  mockListings,
  setMockListings,
  mockSales,
  mockAccounts,
} from './mockState';

export async function proposeOffer(itemId: string, price: number, message?: string): Promise<Offer> {
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

export async function counterOffer(offerId: string, price: number, message?: string): Promise<Offer> {
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

export async function respondToOffer(_offerId: string, _accept: boolean, _message?: string): Promise<void> {
  /* no-op */
}

export async function cancelOffer(_offerId: string): Promise<void> {
  /* no-op */
}

export async function listActiveOffers(): Promise<Offer[]> {
  return [];
}

export async function listDealHistory(): Promise<Offer[]> {
  return [];
}

export async function getOfferDetail(offerId: string): Promise<{ offer: Offer; events: OfferEvent[] }> {
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

export async function getUserReputation(userId: string): Promise<UserReputation> {
  return {
    userId,
    avgStars: 4.5,
    totalRatings: 0,
    completedDeals: 0,
  };
}

export async function toggleForSale(_itemId: string, _forSale: boolean, _askingPrice?: number): Promise<void> {
  /* no-op */
}

export async function markShipped(_offerId: string, _trackingInfo?: string): Promise<void> {
  /* no-op */
}

export async function completeDeal(_offerId: string, _stars: number, _comment?: string): Promise<void> {
  /* no-op */
}

// ─── Multi-Marketplace Selling ──────────────────────────────────────────────

export async function listMarketplaceListings(): Promise<MarketplaceListing[]> {
  return mockListings;
}

export async function createMarketplaceListing(input: Omit<MarketplaceListing, 'id' | 'viewsCount' | 'watchersCount' | 'offersCount' | 'createdAt'>): Promise<MarketplaceListing> {
  const listing = { ...input, id: `mock-listing-${Date.now()}`, viewsCount: 0, watchersCount: 0, offersCount: 0, createdAt: new Date().toISOString() } as MarketplaceListing;
  mockListings.unshift(listing);
  return listing;
}

export async function updateMarketplaceListing(_listingId: string, _patch: Partial<MarketplaceListing>): Promise<MarketplaceListing> {
  throw new Error('Not implemented');
}

export async function deleteMarketplaceListing(listingId: string): Promise<void> {
  setMockListings(mockListings.filter((l) => l.id !== listingId));
}

export async function listMarketplaceAccounts(): Promise<MarketplaceAccount[]> {
  return mockAccounts;
}

export async function listMarketplaceSales(): Promise<MarketplaceSale[]> {
  return mockSales;
}

export async function getMarketplaceFeeSchedules(): Promise<MarketplaceFeeSchedule[]> {
  return [
    { marketplaceId: 'collectai', displayName: 'CollectAI P2P', baseFeePct: 0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: 'Free P2P trading' },
    { marketplaceId: 'ebay', displayName: 'eBay', baseFeePct: 12.9, paymentProcessingPct: 2.9, fixedFee: 0.30, currency: 'EUR', notes: 'Final value fee + payment processing' },
    { marketplaceId: 'mercari', displayName: 'Mercari', baseFeePct: 10.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: 'Flat 10% seller fee' },
    { marketplaceId: 'cardmarket', displayName: 'Cardmarket', baseFeePct: 5.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: '5% commission' },
    { marketplaceId: 'stockx', displayName: 'StockX', baseFeePct: 9.5, paymentProcessingPct: 3.0, fixedFee: 0, currency: 'EUR', notes: 'Transaction + payment processing' },
    { marketplaceId: 'bricklink', displayName: 'BrickLink', baseFeePct: 3.0, paymentProcessingPct: 0, fixedFee: 0, currency: 'EUR', notes: '3% final value fee' },
  ];
}
