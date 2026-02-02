/**
 * Shared types for DataProvider abstraction.
 * These are the stable shapes returned to UI — no raw Supabase responses.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Taxonomy Types (Hybrid Architecture)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Price band with quantiles and confidence.
 * q10/q50/q90 represent 10th, 50th (median), and 90th percentile estimates.
 */
export type PriceBand = {
  q10: number;
  q50: number;
  q90: number;
  confidence: number;  // 0.0 - 1.0
  currency: string;
};

/**
 * Taxonomy classification result.
 * Returned from mapping operations.
 */
export type TaxonomyClassification = {
  categoryId: string;
  subtypeId: string;
  taxonomyVersion: string;
  collections: string[];  // Orthogonal collection tags (e.g., 'taylor_swift', 'bts')
  confidence: number;
  rationale?: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Core Types
// ─────────────────────────────────────────────────────────────────────────────

export type PortfolioSummary = {
  total: number;
  deltaPct: number;
  itemCount: number;
};

export type Item = {
  id: string;
  name: string;
  category: string;
  subtypeId?: string;           // Finer granularity (e.g., 'warhammer_books')
  taxonomyVersion?: string;     // Version of taxonomy used for classification
  collections?: string[];       // Collection tags (e.g., ['taylor_swift', 'eras_tour'])
  price: number;
  priceBand?: PriceBand;        // q10/q50/q90 price estimates
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
  category?: string;
  notes?: string;
  createdAt?: string;
};

export type CreateWatchlistInput = {
  title: string;
  category: string;
  targetPrice?: number | null;
  notes?: string;
  priority?: 'high' | 'medium' | 'low';
};

// Alias for backwards compatibility
export type CreateWishlistInput = CreateWatchlistInput;

export type CreateItemInput = {
  name: string;
  category: string;
  subtypeId?: string;
  taxonomyVersion?: string;
  collections?: string[];
  price: number;
  priceBand?: PriceBand;
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
  explanation?: string | null;
};

export type QuickScanResult = {
  itemId?: string | null;
  attributes: QuickScanAttributes;
  prediction: QuickScanPrediction;
  taxonomy?: TaxonomyClassification;  // Classification with subtype and collections
};

// ─────────────────────────────────────────────────────────────────────────────
// Barcode / Market Data Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Result from barcode/ISBN lookup.
 * Prefills item data from product databases or market search.
 */
export type BarcodeLookupResult = {
  /** Matched product title */
  title?: string | null;
  /** Detected category (e.g., 'music_media', 'warhammer', 'books') */
  categoryId?: string | null;
  /** Subtype within category (e.g., 'signed_media', 'album', 'rulebook') */
  subtypeId?: string | null;
  /** Taxonomy version used for classification */
  taxonomyVersion?: string;
  /** Collection tags (e.g., ['bts', 'proof_album'], ['taylor_swift', 'eras_tour']) */
  collections?: string[];
  /** Extracted attributes (artist, ISBN, publisher, etc.) */
  attributes?: Record<string, unknown>;
  /** Required attributes that are still missing */
  missingRequired?: string[];
  /** Price band estimate from market data */
  priceBand?: PriceBand | null;
  /** Explanation of how price/category was determined */
  rationale?: string[];
  /** Original barcode value */
  barcode?: string;
  /** Barcode type (ean13, upc_a, isbn, etc.) */
  barcodeType?: string;
  /** Image URL if found */
  imageUrl?: string | null;
};

/**
 * Normalized market hit from any provider (eBay, TCGPlayer, etc.).
 * Used for price comparisons and sold comps.
 */
export type MarketHit = {
  /** Source provider (e.g., 'ebay', 'tcgplayer', 'discogs') */
  source: string;
  /** Provider's listing ID */
  rawId: string;
  /** Listing title */
  title: string;
  /** Price in source currency */
  price: number;
  /** Currency code (EUR, USD, GBP) */
  currency: string;
  /** Sale/end date if sold */
  soldAt?: string | null;
  /** Listing URL */
  url?: string | null;
  /** Condition description */
  condition?: string | null;
  /** Image URL */
  imageUrl?: string | null;
  /** Hash of raw payload for deduplication */
  rawPayloadHash?: string;
};

/**
 * Options for market search.
 */
export type MarketSearchOptions = {
  /** Filter by category */
  categoryId?: string;
  /** Filter by subtype */
  subtypeId?: string;
  /** Filter by collection tags */
  collections?: string[];
  /** Max results per provider */
  limit?: number;
  /** Only include sold items */
  soldOnly?: boolean;
  /** Minimum price filter */
  minPrice?: number;
  /** Maximum price filter */
  maxPrice?: number;
};

/**
 * Aggregated market search result.
 */
export type MarketSearchResult = {
  /** Combined hits from all providers */
  hits: MarketHit[];
  /** Which providers were queried */
  providers: string[];
  /** Total hits before deduplication */
  totalRaw: number;
  /** Confidence in results (0-1) */
  confidence: number;
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

/**
 * DM thread status.
 */
export type DmThreadStatus = 'pending' | 'accepted' | 'declined';

/**
 * DM thread — from v_chat_inbox_v1 view.
 */
export type DmThread = {
  id: string;
  otherUserId: string;
  otherUserName: string;
  otherUserHandle?: string | null;
  otherUserAvatarUrl?: string | null;
  otherUserAvatarColor?: string;
  status: DmThreadStatus;
  lastMessagePreview?: string | null;
  lastMessageAt?: string | null;
  unreadCount: number;
  isIncoming: boolean; // true if other user initiated
};

/**
 * Incoming DM request (pending threads where we are the recipient).
 */
export type DmRequest = {
  threadId: string;
  fromUserId: string;
  fromUserName: string;
  fromUserHandle?: string | null;
  fromUserAvatarUrl?: string | null;
  fromUserAvatarColor?: string;
  requestMessage?: string | null;
  requestedAt: string;
};

/**
 * DM message — individual message in a thread.
 */
export type DmMessage = {
  id: string;
  threadId: string;
  authorUserId: string;
  text: string;
  createdAt: string;
};

/**
 * Analytics metrics for the Analytics screen.
 * Combines build/paint project stats and Twitch creator stats.
 */
export type AnalyticsMetrics = {
  // Build & paint
  activeProjects: number;
  backlogProjects: number;
  completedProjects: number;
  totalBuildMinutes: number;
  totalBuildHours: number;
  // Twitch
  twitchCreatorsTracked: number;
  twitchCreatorsLive: number;
};

/**
 * Category summary for browsing list.
 * Shows completion progress and counts.
 */
export type CategorySummary = {
  id: string;
  name: string;
  completionPct: number;
  ownedCount: number;
  missingCount: number;
  totalCount: number;
};

/**
 * Missing item in a category checklist.
 * Items the user doesn't own yet.
 */
export type CategoryMissingItem = {
  id: string;
  categoryId: string;
  title: string;
  brand?: string | null;
  notes?: string | null;
};

/**
 * Alert feed item — from v_alerts_feed_v1 view.
 * Represents a triggered alert event (price drop, restock, etc.).
 */
export type AlertFeedItem = {
  id: string;
  type: string; // price_drop | price_spike | restock | drop_detected | completeness | rarity
  title: string;
  body?: string | null;
  createdAt: string;
  itemId?: string | null;
  watchlistItemId?: string | null;
};

/**
 * QuickScan draft — data captured from scan before persisting.
 */
export type QuickscanDraft = {
  photoUri: string;
  categoryId?: string | null;
  title?: string | null;
  attributes?: Record<string, any> | null;
  notes?: string | null;
};

/**
 * Persisted item — minimal DTO returned after creating an item.
 */
export type PersistedItem = {
  id: string;
  title: string;
  categoryId: string;
  createdAt: string;
  imageUrl?: string | null;
};

// ─────────────────────────────────────────────────────────────────────────────
// Build & Paint Projects
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Build & paint project — from v_build_paint_projects_v1 view.
 */
export type BuildPaintProject = {
  id: string;
  title: string;
  category?: string | null;
  status?: string | null;
  percent: number;
  isCompleted: boolean;
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
};

/**
 * Build & paint project step — from v_build_paint_project_steps_v1 view.
 */
export type BuildPaintStep = {
  id: string;
  projectId: string;
  title: string;
  isDone: boolean;
  sortOrder: number;
  createdAt: string;
};

/**
 * Build & paint project note — from v_build_paint_project_notes_v1 view.
 */
export type BuildPaintNote = {
  id: string;
  projectId: string;
  body: string;
  createdAt: string;
};

/**
 * Input for creating a new build & paint project.
 */
export type CreateBuildPaintProjectInput = {
  title: string;
  category?: string | null;
};
