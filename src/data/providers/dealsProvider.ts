/**
 * Deals domain provider — P2P offers, marketplace listings, sales.
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
import { collectorsApi } from '../../api/collectorsApi';

export async function proposeOffer(itemId: string, price: number, message?: string): Promise<Offer> {
  return collectorsApi.proposeOffer({ item_id: itemId, price, message }) as Promise<Offer>;
}

export async function counterOffer(offerId: string, price: number, message?: string): Promise<Offer> {
  return collectorsApi.counterOffer(offerId, { price, message }) as Promise<Offer>;
}

export async function respondToOffer(offerId: string, accept: boolean, message?: string): Promise<void> {
  await collectorsApi.respondToOffer(offerId, { accept, message });
}

export async function cancelOffer(offerId: string): Promise<void> {
  await collectorsApi.cancelOffer(offerId);
}

export async function listActiveOffers(): Promise<Offer[]> {
  const result = await collectorsApi.listActiveOffers() as { offers?: Offer[]; total_count?: number } | Offer[];
  return Array.isArray(result) ? result : (result?.offers ?? []);
}

export async function listDealHistory(): Promise<Offer[]> {
  const result = await collectorsApi.listDealHistory() as { offers?: Offer[]; total_count?: number } | Offer[];
  return Array.isArray(result) ? result : (result?.offers ?? []);
}

export async function getOfferDetail(offerId: string): Promise<{ offer: Offer; events: OfferEvent[] }> {
  return collectorsApi.getOfferDetail(offerId) as Promise<{ offer: Offer; events: OfferEvent[] }>;
}

export async function getUserReputation(userId: string): Promise<UserReputation> {
  return collectorsApi.getUserReputation(userId) as Promise<UserReputation>;
}

export async function toggleForSale(itemId: string, forSale: boolean, askingPrice?: number): Promise<void> {
  await collectorsApi.toggleItemForSale(itemId, { for_sale: forSale, asking_price: askingPrice });
}

export async function markShipped(offerId: string, trackingInfo?: string): Promise<void> {
  await collectorsApi.markShipped(offerId, { tracking_info: trackingInfo });
}

export async function completeDeal(offerId: string, stars: number, comment?: string): Promise<void> {
  await collectorsApi.completeDeal(offerId, { stars, comment });
}

// Multi-Marketplace Selling
/**
 * These two endpoints return an ENVELOPE, not a bare array:
 *   GET /marketplace/listings       -> { listings: [...], total_count }
 *   GET /marketplace/listings/sales -> { sales: [...],    total_count }
 * while /accounts and /fees return bare arrays. The signatures here promised
 * arrays for all four, so the Seller Dashboard got an object, and
 * `for (const s of sales)` threw `TypeError: iterator method is not callable`
 * — the whole screen fell into its ScreenErrorBoundary ("Seller Dashboard
 * failed to load"). `?? []` did not save it: an object is truthy.
 * Verified against prod 2026-08-01 with a real user token.
 */
function unwrap<T>(res: unknown, key: string): T[] {
  if (Array.isArray(res)) return res as T[];
  const inner = (res as Record<string, unknown> | null)?.[key];
  return Array.isArray(inner) ? (inner as T[]) : [];
}

export async function listMarketplaceListings(status?: MarketplaceListing['status']): Promise<MarketplaceListing[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return unwrap<MarketplaceListing>(await collectorsApi.get(`/marketplace/listings${qs}`), 'listings');
}

export async function createMarketplaceListing(input: Omit<MarketplaceListing, 'id' | 'viewsCount' | 'watchersCount' | 'offersCount' | 'createdAt'>): Promise<MarketplaceListing> {
  return collectorsApi.post('/marketplace/listings', input as Record<string, unknown>);
}

export async function updateMarketplaceListing(listingId: string, patch: Partial<MarketplaceListing>): Promise<MarketplaceListing> {
  return collectorsApi.patch(`/marketplace/listings/${listingId}`, patch as Record<string, unknown>);
}

export async function deleteMarketplaceListing(listingId: string): Promise<void> {
  await collectorsApi.delete(`/marketplace/listings/${listingId}`);
}

export async function listMarketplaceAccounts(): Promise<MarketplaceAccount[]> {
  // Bare array today, but unwrap defensively so an envelope added later cannot
  // reintroduce the crash above.
  return unwrap<MarketplaceAccount>(await collectorsApi.get('/marketplace/listings/accounts'), 'accounts');
}

export async function listMarketplaceSales(): Promise<MarketplaceSale[]> {
  return unwrap<MarketplaceSale>(await collectorsApi.get('/marketplace/listings/sales'), 'sales');
}

export async function getMarketplaceFeeSchedules(): Promise<MarketplaceFeeSchedule[]> {
  return unwrap<MarketplaceFeeSchedule>(await collectorsApi.get('/marketplace/listings/fees'), 'fee_schedules');
}
