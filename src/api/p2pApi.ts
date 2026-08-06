/**
 * P2P marketplace API client — member-to-member listings (Stage 1: no payments).
 *
 * Mirrors server/app/features/p2p_listing_router.py. See
 * docs/P2P_MARKETPLACE_SPEC.md for why Stage 1 deliberately has no checkout.
 *
 * Field names are snake_case because they cross the wire verbatim — the server
 * returns exactly these keys. Do not camelise here; map at the screen boundary
 * if a screen wants camelCase, the way dataProvider does elsewhere.
 */
import { get, post } from './httpClient';

/** Listing lifecycle. MUST match marketplace_listings_status_check, which
 *  allows draft | active | sold | expired | delisted | error. 'withdrawn' is
 *  NOT legal — it raised a CheckViolationError during the build. */
export type P2PListingStatus = 'active' | 'sold' | 'delisted';

export type P2PListing = {
  id: string;
  user_id: string;
  item_id: string | null;
  title: string;
  description: string | null;
  price: number;
  currency: string;
  condition_label: string | null;
  category: string | null;
  /** Bare canonical key (e.g. `azu-azurite-sea-booster-box`). The server
   *  namespaces it to `<category>:<key>` when writing the market_hits row —
   *  see learning_canonical_key_vs_item_ref_namespace. */
  canonical_key: string | null;
  ships_from: string | null;
  shipping_cost: number | null;
  /** Thumbnail from the source item. The grid is photo-first because the
   *  thumbnail drives the click — a grid without images is just a list. Null
   *  when the item has no photo, so callers must render a placeholder. */
  image_url: string | null;
  /** True when `image_url` is a CATALOG image, not the seller's photo.
   *  Must be labelled in the UI — a stock photo passed off as the actual item
   *  hides condition, which is the one thing a second-hand buyer needs. */
  image_is_catalog: boolean;
  /** Seller credibility. No transactions exist in Stage 1, so these are the
   *  signals we genuinely have — deliberately NOT ratings, which would be
   *  gameable without a payment record and would imply vetting we don't do.
   *  `seller_name` can be null when a profile has no display name set. */
  seller_name: string | null;
  seller_since: string | null;
  seller_collection_size: number;
  seller_active_listings: number;
  /** Demand — the differentiator. `watchers_above_price` are members who
   *  would get a Target Hit for this listing right now. */
  watchers: number;
  watchers_above_price: number;
  status: string;
  created_at: string | null;
  is_mine: boolean;
};

/**
 * List an item you own. `item_id` is required — a listing derived from an
 * owned item inherits canonical_key + category, which is what lets it match
 * Target Hit's exact-identity arm instead of the fuzzy title arm.
 *
 * Throws on non-2xx (httpClient behaviour). Callers must handle:
 *   409 ALREADY_LISTED  — this item already has an active listing
 *   404 ITEM_NOT_FOUND  — not in the caller's collection (ownership is
 *                         enforced server-side; do not rely on hiding the UI)
 */
export const createListing = (payload: {
  item_id: string;
  price: number;
  currency?: string;
  condition_label?: string;
  condition_notes?: string;
  description?: string;
  ships_from?: string;
  shipping_cost?: number;
}) => post<P2PListing>('/p2p/listings', payload);

/** Browse active member listings. `canonical_key` powers "other members
 *  selling this" on a catalog item page. */
export const listListings = (params?: {
  category?: string;
  canonical_key?: string;
  mine?: boolean;
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.category) q.set('category', params.category);
  if (params?.canonical_key) q.set('canonical_key', params.canonical_key);
  if (params?.mine) q.set('mine', 'true');
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  const qs = q.toString();
  return get<{ listings: P2PListing[] }>(`/p2p/listings${qs ? `?${qs}` : ''}`);
};

/**
 * Resolve one listing — the target of the `sparrowcollect.com/l/<id>` URL that
 * a Target Hit opens for a member listing.
 *
 * Returns sold/delisted listings too, with their real `status`, so the screen
 * can say "this has been sold" instead of showing a 404. A buyer who taps an
 * alert deserves to know the item went, not that something broke.
 */
export const getListing = (listingId: string) =>
  get<P2PListing>(`/p2p/listings/${encodeURIComponent(listingId)}`);

/**
 * Mark a listing sold or delisted.
 *
 * The server removes the corresponding `market_hits` row SYNCHRONOUSLY here
 * (unlike publish, which is fire-and-forget), so by the time this resolves the
 * listing can no longer produce a Target Hit. A snipe that opens a sold
 * listing spends the user's daily alert and their trust.
 */
export const delistListing = (listingId: string, status: 'sold' | 'delisted' = 'sold') =>
  post<{ ok: boolean; status: string }>(
    `/p2p/listings/${encodeURIComponent(listingId)}/delist?status=${status}`,
    {},
  );

/** Report a listing. DSA notice-and-action — the micro-enterprise exemption
 *  does not cover this, so it ships in Stage 1. Re-reporting the same listing
 *  is a no-op server-side and does NOT inflate the moderation counter. */
export const reportListing = (listingId: string, reason: string, detail?: string) =>
  post<{ ok: boolean }>(
    `/p2p/listings/${encodeURIComponent(listingId)}/report`,
    { reason, detail },
  );


// ── Demand (pre-listing) ────────────────────────────────────────────────────

export type DemandPreview = {
  watchers: number;
  watchers_above_price: number;
  top_target: number | null;
  /** False => the item has no canonical_key, so it cannot be joined to any
   *  watchlist. Show the catalog-match prompt, NOT a discouraging "0 watching"
   *  which would be meaningless rather than informative. */
  is_catalog_matched: boolean;
};

/** Who is waiting for an item you own, before you list it. Ownership is
 *  enforced server-side — demand is competitive information. */
export const getDemandPreview = (itemId: string, price?: number) =>
  get<DemandPreview>(
    `/p2p/demand/${encodeURIComponent(itemId)}${price ? `?price=${price}` : ''}`,
  );

// ── Stage 2: offers, completion, grading ───────────────────────────────────

export type P2POffer = {
  id: string;
  listing_id: string;
  listing_title: string | null;
  buyer_id: string;
  seller_id: string;
  amount: number;
  currency: string;
  /** pending | countered | accepted | declined | cancelled | expired |
   *  shipped | completed. Mirrors p2p_offers_status_check. */
  status: string;
  message: string | null;
  counter_count: number;
  created_at: string | null;
  seller_confirmed_at: string | null;
  buyer_confirmed_at: string | null;
  i_am_buyer: boolean;
  /** Server-computed so the client never re-derives the state machine. */
  can_confirm: boolean;
  can_grade: boolean;
  already_graded: boolean;
};

export const createOffer = (payload: {
  listing_id: string;
  amount: number;
  currency?: string;
  message?: string;
}) => post<P2POffer>('/p2p/offers', payload);

export const listOffers = (role: 'all' | 'buying' | 'selling' = 'all') =>
  get<{ offers: P2POffer[] }>(`/p2p/offers?role=${role}`);

/**
 * Accept, decline, counter or withdraw.
 *
 * `accept` marks the listing reserved but does NOT take it off the market —
 * with no payment rail a hard reserve is unenforceable. `withdraw` is
 * available to either side after an accept and records who walked, which
 * feeds reputation.
 */
export const respondToOffer = (
  offerId: string,
  action: 'accept' | 'decline' | 'counter' | 'withdraw',
  amount?: number,
) =>
  post<P2POffer>(
    `/p2p/offers/${encodeURIComponent(offerId)}/respond?action=${action}` +
      (amount != null ? `&amount=${amount}` : ''),
    {},
  );

/** Confirm your side. Seller marks sent, buyer marks received; both => the
 *  trade completes and grading unlocks. */
export const confirmExchange = (offerId: string) =>
  post<P2POffer>(`/p2p/offers/${encodeURIComponent(offerId)}/confirm`, {});

/** Grade the counterparty. Only possible after two-sided completion — the
 *  server enforces it and so does the DB. */
export const gradeCounterparty = (
  offerId: string,
  verdict: 'positive' | 'negative',
  note?: string,
) => post<{ ok: boolean }>(`/p2p/offers/${encodeURIComponent(offerId)}/grade`, { verdict, note });

export type MemberReputation = {
  user_id: string;
  total_grades: number;
  positive_grades: number;
  /** null below 3 grades — one grade is a coin flip, not a reputation. */
  positive_pct: number | null;
  completed_trades: number;
  withdrawn_count: number;
};

export const getMemberReputation = (memberId: string) =>
  get<MemberReputation>(`/p2p/members/${encodeURIComponent(memberId)}/reputation`);
