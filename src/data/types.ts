/**
 * Shared types for DataProvider abstraction.
 * These are the stable shapes returned to UI — no raw Supabase responses.
 */

export type PortfolioSummary = {
  total: number;
  deltaPct: number;
  itemCount: number;
};

export type Item = {
  id: string;
  name: string;
  category: string;
  price: number;
  imageUrl?: string;
  updatedAt?: string;
};

export type WatchlistItem = {
  id: string;
  title: string;
  priority: 'high' | 'medium' | 'low';
  owned: boolean;
  targetPrice: number | null;
  currency: string;
};

export type CreateItemInput = {
  name: string;
  category: string;
  price: number;
  imageUrl?: string;
};

/**
 * Public user profile — from user_public_profile_v1 view (RLS: public SELECT).
 * Only contains fields safe for public display.
 */
export type PublicUserProfile = {
  id: string;
  displayName: string;
  handle?: string | null;
  avatarUrl?: string | null;
  bio?: string | null;
  interests?: string[] | null;
  collectionCount?: number | null;
  collectionValueEur?: number | null;
};

/**
 * QuickScan types — matches backend /quickscan-advanced/single response.
 */
export type QuickScanAttributes = {
  category: string;
  editionGuess?: string | null;
  conditionGuess?: string | null;
  rarityScore?: number | null;
};

export type QuickScanPrediction = {
  name: string;
  estimatedLow: number;
  estimatedMid: number;
  estimatedHigh: number;
  currency: string;
  confidence: number;
};

export type QuickScanResult = {
  itemId?: string | null;
  attributes: QuickScanAttributes;
  prediction: QuickScanPrediction;
};

/**
 * Spotlight slide for category store carousel.
 */
export type SpotlightSlide = {
  id: string;
  title: string;
  subtitle?: string;
  imageUrl?: string;
  linkType: 'item' | 'event' | 'external';
  linkId?: string;
  linkUrl?: string;
};

/**
 * Mini user profile for "Friends who follow" section.
 */
export type MiniUserProfile = {
  id: string;
  displayName: string;
  avatarUrl?: string | null;
  avatarColor?: string;
};

/**
 * Category store data — Amazon Brand Store style layout.
 */
export type CategoryStoreData = {
  categoryId: string;
  categoryName: string;
  categoryTagline: string;
  bannerImageUrl?: string;
  spotlightSlides: SpotlightSlide[];
  items: Item[];
  upcomingEvents: {
    id: string;
    title: string;
    kind: 'collection_drop' | 'meetup' | 'stream';
    date: string;
    time?: string;
  }[];
  friendsWhoFollow: MiniUserProfile[];
};
