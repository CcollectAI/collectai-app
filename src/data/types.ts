/**
 * Shared types for DataProvider abstraction.
 * These are the stable shapes returned to UI — no raw Supabase responses.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Pagination
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Optional pagination parameters for list endpoints.
 * When omitted, the provider uses sensible defaults.
 */
export type PaginationParams = {
  limit?: number;
  offset?: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Currency
// ─────────────────────────────────────────────────────────────────────────────

/**
 * ISO 4217 currency codes supported by the app.
 * The 7 supported currencies: EUR, USD, GBP, JPY, KRW, AUD, CAD.
 */
export type CurrencyCode = 'EUR' | 'USD' | 'GBP' | 'JPY' | 'KRW' | 'AUD' | 'CAD';

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
  currency: CurrencyCode;
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

// 'marketplace' is written by the SERVER, not the app: _settle_completed_trade
// stamps it on the row it mints for the buyer when a P2P trade completes. The
// column has no CHECK constraint, so this union was the only thing standing
// between that value and every reader — and it did not list it, which made a
// legitimate row's source read as an impossible value.
export type ItemSource = 'ai' | 'scan' | 'manual' | 'marketplace';

export type Item = {
  id: string;
  name: string;
  category: string;
  source?: ItemSource;          // 'ai' = QuickScan+catalog match, 'scan' = low-conf scan, 'manual' = user-added
  subtypeId?: string;           // Finer granularity (e.g., 'warhammer_books')
  taxonomyVersion?: string;     // Version of taxonomy used for classification
  collections?: string[];       // Collection tags (e.g., ['taylor_swift', 'eras_tour'])
  attributesJson?: Record<string, unknown>;  // Category-specific attributes (condition, grade, etc.)
  price: number;
  priceBand?: PriceBand;        // q10/q50/q90 price estimates
  imageUrl?: string;
  updatedAt?: string;
  // Rich detail surfaced on the collection card (POST /items enrichment,
  // 2026-07-15). All optional — legacy or QuickScan-only items may lack them.
  condition?: string;           // e.g. "Near Mint", "PSA 9"
  brand?: string;               // manufacturer / publisher
  year?: number;                // release year
  series?: string;              // set / series name
  editionLabel?: string;        // e.g. "1st Edition", "Limited"
  // Acquisition / "what I paid" fields. Captured at add-manual time and stored
  // in the items table; until 2026-05-01 they were never read back into the
  // Item shape, so the items screen showed predicted price only and the user's
  // actual cost was invisible. Optional: items added before this surface
  // existed, or added via QuickScan without a price entered, will be undefined.
  purchasePriceEur?: number | null;     // EUR-normalized cost basis
  purchaseCurrency?: CurrencyCode | null;  // currency at time of purchase (display only)
  purchasedAt?: string | null;          // ISO date string of acquisition
  purchaseNotes?: string | null;        // free-text receipt/memo
};

export type WatchlistItem = {
  id: string;
  title: string;
  priority: 'high' | 'medium' | 'low';
  owned: boolean;
  targetPrice: number | null;
  currency: CurrencyCode;
  category?: string;
  notes?: string;
  createdAt?: string;
  lastMarketPrice?: number | null;
  lastCheckedAt?: string | null;
  priceTrend?: 'up' | 'down' | 'stable' | null;
  marketHitCount?: number;
  sortOrder?: number;
};

export type CreateWatchlistInput = {
  title: string;
  category: string;
  targetPrice?: number | null;
  /**
   * The currency `targetPrice` is expressed in. Defaults to EUR when omitted.
   *
   * It has to travel WITH the number. `watchlist_items.currency` exists and the
   * server has always accepted it, but `addWatchlistItem` hardcoded 'EUR' — so
   * watching a JPY 8000 listing stored `target_price = 8000, currency = 'EUR'`
   * and Target Hit compared 8000 EUR, ~164x too generous, firing on almost
   * anything in the category.
   */
  targetPriceCurrency?: string | null;
  notes?: string;
  priority?: 'high' | 'medium' | 'low';
  /**
   * Reference to what is being watched — a catalog `item_key` when the add came
   * from a catalog screen. Maps to `watchlist_items.item_id` (a TEXT column, so
   * catalog keys are valid there; it is NOT `items.id`).
   *
   * The server has accepted `item_id` on POST /watchlist/mine all along, but
   * this type had no slot for it, so every add wrote NULL — all 12 production
   * rows had `item_id IS NULL` and no watchlist row could be traced back to
   * what it watches. Free-text adds (wishlist form, watchlist-builder) have no
   * reference and correctly leave this undefined.
   */
  itemId?: string | null;
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
  // Rich detail so the saved item lands as a FULL card (see POST /items).
  // Populated by QuickScan / catalog-match / the manual form.
  notes?: string;
  canonicalKey?: string;
  brand?: string;
  condition?: string;
  year?: number;
  series?: string;
  editionLabel?: string;
  /** Category-specific attributes (rarity, set_code, edition, print run, …). */
  attributes?: Record<string, unknown>;
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
  /** Category-specific extracted details from vision AI (e.g. set_name, card_number, rarity) */
  extractedDetails?: Record<string, string | number | boolean | null> | null;
};

export type QuickScanPrediction = {
  name: string;
  estimatedLow: number;
  estimatedMid: number;
  estimatedHigh: number;
  currency: CurrencyCode;
  confidence: number;
  explanation?: string | null;
};

export type CatalogAlternative = {
  catalogItemId: string | null;
  itemKey: string | null;
  title: string | null;
  category: string | null;
  brand: string | null;
  rarity: string | null;
  setCode: string | null;
  /** R50k: catalog reference images are backend-only; mobile app does not render them. */
  hasReferenceImage?: boolean;
  matchScore: number;
  matchReason: string | null;
};

export type FieldConfidence = {
  category: number;
  name: number;
  condition: number;
};

export type QuickScanResult = {
  itemId?: string | null;
  attributes: QuickScanAttributes;
  prediction: QuickScanPrediction;
  taxonomy?: TaxonomyClassification;  // Classification with subtype and collections
  catalogMatchId?: string | null;
  catalogMatchKey?: string | null;
  alternatives?: CatalogAlternative[];
  fieldConfidence?: FieldConfidence | null;
  // QuickScan enhancement fields
  scanSessionId?: string | null;
  socialProof?: SocialProof | null;
  duplicateInfo?: DuplicateInfo | null;
  defectAnnotations?: DefectAnnotation[];
  suggestedGrade?: SuggestedGrade | null;
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
  /** Currency code (EUR, USD, GBP, etc.) */
  currency: CurrencyCode;
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
  /**
   * True when `price` is a current asking/listing price (not a sold comp).
   * Consumers should label these differently (e.g. "Asking €X" vs "Sold €X")
   * and avoid using them as sold-comp training signal.
   */
  isListing?: boolean;
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
    kind: 'collection_drop' | 'meetup' | 'stream' | 'convention' | 'release';
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
  readAt?: string | null;
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
  /** The price the alert actually fired on, from `alert_trigger_history.trigger_value`.
   *  Was dropped in the mapping, so the Home watchlist card rendered a hardcoded
   *  `value: 0` — every row showed EUR 0 next to it. */
  price?: number | null;
  /** The user's target, for the same reason. */
  targetPrice?: number | null;
};

/**
 * A standing alert *rule* the user configured — distinct from AlertFeedItem,
 * which is a record of a rule having fired.
 *
 * The Alerts screen's "Rules" tab rendered AlertFeedItem until 2026-07-30, so
 * it showed the same trigger history as the "Triggers" tab, could never show a
 * rule, and its swipe-to-delete sent a trigger-history id to
 * DELETE /alerts/mine/{alert_id} (a 404 every time). Rules come from
 * GET /alerts/mine; keep the two types separate so they cannot be crossed again.
 */
export type AlertRule = {
  id: string;
  itemId: string | null;
  category: string | null;
  triggerType: string;
  thresholdValue: number | null;
  direction: 'up' | 'down' | null;
  active: boolean;
  createdAt: string;
};

/**
 * QuickScan draft — data captured from scan before persisting.
 */
export type QuickscanDraft = {
  photoUri: string;
  categoryId?: string | null;
  title?: string | null;
  attributes?: Record<string, unknown> | null;
  notes?: string | null;
  // Catalog match key from the intake response (catalog_match_key). When set,
  // POST /items writes it to items.canonical_key so downstream JOINs against
  // price_predictions / price_history / valuation pipelines can find the
  // matched catalog row. Without this, every Premium feature that JOINs
  // items → catalog returns empty for paid users. Added 2026-05-02.
  canonicalKey?: string | null;
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
export type PaintEntry = { brand: string; color: string; type: string };
export type PaintRecipe = { name: string; paints: PaintEntry[]; notes: string };

export type BuildPaintProject = {
  id: string;
  title: string;
  category?: string | null;
  categoryId?: string | null;
  itemId?: string | null;
  itemName?: string | null;
  itemImageUrl?: string | null;
  status?: string | null;
  percent: number;
  isCompleted: boolean;
  notes?: string | null;
  imageUrl?: string | null;
  paintRecipes?: PaintRecipe[] | null;
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
  categoryId?: string | null;
  itemId?: string | null;
};

// ─────────────────────────────────────────────────────────────────────────────
// Smart Deal Agent Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Purchase mandate — user-defined buying criteria for the Smart Deal Agent.
 */
export type PurchaseMandate = {
  id: string;
  userId: string;
  name: string;
  status: 'active' | 'paused' | 'exhausted' | 'expired';

  // Search criteria
  searchQuery: string;
  category?: string | null;
  conditionFilter: string[];
  minTrustScore: number;

  // Spending controls
  maxPrice: number;
  maxTotalBudget?: number | null;
  spentTotal: number;
  cooldownHours: number;

  // Marketplace preferences
  allowedSources: string[];
  region?: string | null;

  // Lifecycle
  expiresAt?: string | null;
  lastScanAt?: string | null;
  lastDealAt?: string | null;
  dealsFound: number;
  dealsPurchased: number;
  createdAt: string;
  updatedAt: string;
};

/**
 * Input for creating a new purchase mandate.
 */
export type CreateMandateInput = {
  name: string;
  searchQuery: string;
  category?: string | null;
  conditionFilter?: string[];
  minTrustScore?: number;
  maxPrice: number;
  maxTotalBudget?: number | null;
  cooldownHours?: number;
  allowedSources?: string[];
  region?: string | null;
  expiresAt?: string | null;
};

/**
 * Input for updating an existing mandate.
 */
export type UpdateMandateInput = Partial<Omit<CreateMandateInput, 'searchQuery'>> & {
  status?: 'active' | 'paused';
};

/**
 * Mandate deal — a deal discovered by the Smart Deal Agent.
 */
export type MandateDeal = {
  id: string;
  mandateId: string;
  userId: string;
  status: 'discovered' | 'notified' | 'clicked' | 'purchased' | 'declined' | 'expired';

  // Listing
  listingSource: string;
  listingUrl: string;
  affiliateUrl?: string | null;
  listingTitle: string;
  listingPrice: number;
  listingCurrency: CurrencyCode;
  listingCondition?: string | null;
  listingImageUrl?: string | null;
  listingSeller?: string | null;
  listingEnded: boolean;

  // Scoring
  provenanceScore?: number | null;
  dealScore?: number | null;
  priceVsQ50Pct?: number | null;
  predictedQ50?: number | null;
  predictedQ10?: number | null;
  predictedQ90?: number | null;

  // Policy
  policyPassed: boolean;
  policyReasons: string[];

  // Affiliate
  affiliateSource?: string | null;
  affiliateClick: boolean;
  estimatedCommission?: number | null;

  // Confirmation
  confirmedPrice?: number | null;
  addedItemId?: string | null;

  // Timestamps
  discoveredAt: string;
  notifiedAt?: string | null;
  clickedAt?: string | null;
  purchasedAt?: string | null;
  createdAt: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// User Presence
// ─────────────────────────────────────────────────────────────────────────────

/**
 * User online/offline presence status.
 * Returned from heartbeat/presence RPCs.
 */
export type UserPresence = {
  userId: string;
  lastSeenAt: string;
  isOnline: boolean;
};

// ─────────────────────────────────────────────────────────────────────────────
// Activity Feed
// ─────────────────────────────────────────────────────────────────────────────

export type ActivityType = 'item_added' | 'item_sold' | 'event_rsvp' | 'event_created' | 'project_completed' | 'achievement_earned' | 'category_followed' | 'collection_milestone';

export type ActivityFeedItem = {
  id: string;
  userId: string;
  activityType: ActivityType;
  title: string;
  description?: string | null;
  metadata: Record<string, unknown>;
  isPublic: boolean;
  createdAt: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Deal Desk (P2P Offers)
// ─────────────────────────────────────────────────────────────────────────────

export type OfferStatus = 'proposed' | 'countered' | 'accepted' | 'declined' | 'expired' | 'completed' | 'cancelled';

export type Offer = {
  id: string;
  itemId: string;
  itemTitle: string;
  itemImageUrl?: string | null;
  sellerId: string;
  buyerId: string;
  status: OfferStatus;
  currentPrice: number;
  currency: CurrencyCode;
  otherUserId: string;
  otherUserName: string;
  otherUserAvatarUrl?: string | null;
  dmThreadId: string;
  createdAt: string;
  updatedAt: string;
  expiresAt?: string | null;
};

export type OfferEvent = {
  id: string;
  offerId: string;
  actorId: string;
  eventType: string;
  price?: number | null;
  message?: string | null;
  metadata?: Record<string, unknown>;
  createdAt: string;
};

export type UserReputation = {
  userId: string;
  avgStars: number;
  totalRatings: number;
  completedDeals: number;
};

/**
 * Agent stats summary.
 */
export type DealAgentStats = {
  activeMandates: number;
  totalDealsFound: number;
  totalDealsClicked: number;
  totalDealsPurchased: number;
  totalSavedVsQ50: number;
  moneySavedEur: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Multi-Marketplace Selling
// ─────────────────────────────────────────────────────────────────────────────

export type MarketplaceId = 'collectai' | 'ebay' | 'mercari' | 'cardmarket' | 'stockx' | 'bricklink' | 'tcgplayer' | 'discogs';

export type ListingStatus = 'draft' | 'active' | 'sold' | 'expired' | 'delisted' | 'error';
export type ListingFormat = 'fixed_price' | 'auction' | 'best_offer';
export type SaleStatus = 'pending' | 'paid' | 'shipped' | 'delivered' | 'completed' | 'disputed' | 'refunded';

export type MarketplaceAccount = {
  id: string;
  marketplaceId: MarketplaceId;
  sellerName?: string | null;
  sellerId?: string | null;
  isActive: boolean;
  connectedAt: string;
  lastSyncAt?: string | null;
};

export type MarketplaceListing = {
  id: string;
  itemId: string;
  accountId?: string | null;
  marketplaceId: MarketplaceId;
  externalListingId?: string | null;
  listingUrl?: string | null;
  listingTitle: string;
  listingDescription?: string | null;
  price: number;
  currency: CurrencyCode;
  originalPrice?: number | null;
  format: ListingFormat;
  quantity: number;
  conditionLabel?: string | null;
  conditionNotes?: string | null;
  shippingMethod?: string | null;
  shippingCost?: number | null;
  shipsInternational?: boolean;
  returnsAccepted?: boolean;
  status: ListingStatus;
  statusMessage?: string | null;
  viewsCount: number;
  watchersCount: number;
  offersCount: number;
  estimatedFees?: number | null;
  estimatedNet?: number | null;
  feePercentage?: number | null;
  listedAt?: string | null;
  expiresAt?: string | null;
  soldAt?: string | null;
  syncedAt?: string | null;
  createdAt: string;
};

export type MarketplaceSale = {
  id: string;
  listingId: string;
  buyerName?: string | null;
  salePrice: number;
  currency: CurrencyCode;
  shippingCostActual?: number | null;
  platformFee?: number | null;
  paymentProcessingFee?: number | null;
  netProceeds: number;
  trackingNumber?: string | null;
  carrier?: string | null;
  status: SaleStatus;
  soldAt: string;
};

export type MarketplaceFeeSchedule = {
  marketplaceId: MarketplaceId;
  displayName: string;
  baseFeePct: number;
  paymentProcessingPct: number;
  fixedFee: number;
  currency: string;
  notes?: string | null;
};

// ─────────────────────────────────────────────────────────────────────────────
// QuickScan Enhancement Types
// ─────────────────────────────────────────────────────────────────────────────

/** Defect annotation from AI vision analysis. */
export type DefectAnnotation = {
  type: string;
  severity: 'minor' | 'moderate' | 'major' | 'severe';
  location: string;
  description: string;
};

/** Suggested grade from AI vision analysis. */
export type SuggestedGrade = {
  scale: 'psa' | 'cgc' | 'generic';
  gradeValue: string;
  reasoning: string;
};

/** Recent sold item for social proof. */
export type RecentSold = {
  title: string;
  price: number;
  currency: CurrencyCode;
  soldAt: string | null;
  source: string;
};

/**
 * Currently-listed asking price (not a sold comp).
 *
 * Surfaced only for categories where Discogs-style listing data is ingested
 * (vinyl / anime_ost / city_pop etc.). Rendered in Tiffany Blue to visually
 * distinguish from sold comps.
 */
export type RecentListing = {
  title: string;
  price: number;
  currency: CurrencyCode;
  seenAt: string | null;
  source: string;
  url: string | null;
};

/** Scarcity information from supply snapshots. */
export type ScarcityInfo = {
  listingCount: number;
  supplyTrend: 'increasing' | 'stable' | 'decreasing';
  scarcityScore: number;
};

/** Social proof data for scan results. */
export type SocialProof = {
  collectorCount: number;
  isTrending: boolean;
  trendRank: number | null;
  recentSold: RecentSold[];
  recentListings: RecentListing[];
  scarcity: ScarcityInfo;
};

/** Duplicate/variant detection info. */
export type DuplicateInfo = {
  ownedCount: number;
  ownedItemIds: string[];
  isVariant: boolean;
  variantOf: string | null;
  setCompletion: { owned: number; total: number; pct: number } | null;
};

/** Scan feedback submission. */
export type ScanFeedback = {
  scanSessionId: string;
  correctedName?: string | null;
  correctedCategory?: string | null;
  correctedCondition?: string | null;
};

/** Active learning prompt from backend. */
export type ActiveLearningPrompt = {
  question: string;
  options: string[];
  field: 'name' | 'category' | 'condition';
  scanSessionId: string;
};

/** Detected item from multi-item scan. */
export type DetectedMultiItem = {
  itemIndex: number;
  boundingBox: { x: number; y: number; w: number; h: number };
  categoryHint: string | null;
  suggestedName: string | null;
  confidence: number;
};
