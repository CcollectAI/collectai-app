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
import { get, post, patch } from './httpClient';

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
  /** Trade reputation. A grade can only exist against an offer BOTH parties
   *  confirmed, so these are anchored to real two-sided events.
   *
   *  Deliberately not stars: "completed" is two self-confirmations, not a
   *  settled payment, so a 4.7/5 would imply precision the data cannot carry.
   *  `seller_completed_trades` is a fact and is meaningful at 1;
   *  `seller_positive_pct` is null until there are enough grades to mean
   *  anything (the server owns that threshold) — render the count alone in
   *  that case, never "0% positive" off a single grade. */
  seller_completed_trades: number;
  seller_total_grades: number;
  seller_positive_grades: number;
  seller_positive_pct: number | null;
  /** Demand — the differentiator. `watchers_above_price` are members who
   *  would get a Target Hit for this listing right now. */
  watchers: number;
  watchers_above_price: number;
  /** The VIEWER's own watchlist row for this listing's item, or null.
   *
   *  The id rather than a boolean because un-hearting needs it —
   *  `DELETE /watchlist/mine/{watch_id}`. A bool would force the grid to fetch
   *  the whole watchlist just to undo one tap.
   *
   *  Null for anonymous viewers, and null whenever `reaches_target_hit` is
   *  false: the watchlist is keyed on (item_id = canonical_key, category), so a
   *  listing with no canonical identity has nothing to watch and the heart must
   *  not be offered at all. */
  viewer_watch_id: string | null;
  /** False when the listing has no `canonical_key`/`category`, so the publish
   *  supply hook skipped it and it can NEVER fire a Target Hit. The skip is
   *  deliberate (a weakly-identified buyable row only matches the fuzzy title
   *  arm, where false positives live) but it used to be silent: measured
   *  2026-08-07, only 4 of 16 items carry a canonical_key, so most listings
   *  were quietly invisible to the one feature the marketplace exists to feed.
   *  Show this to the seller — it is the difference between a listing that can
   *  reach watchers and one that only reaches browsers. */
  reaches_target_hit: boolean;
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
  /** List something already in your collection. Omit to sell without one. */
  item_id?: string;
  /** Required when `item_id` is omitted — the marketplace-only seller path.
   *  The server creates the item for you (`source='marketplace'`), so photos,
   *  the supply hook and the sold-comp hook all work exactly as they do for a
   *  collection item. */
  title?: string;
  category?: string;
  /** Bare catalogue key. Without it the listing cannot fire a Target Hit —
   *  the response's `reaches_target_hit` reports this back. */
  canonical_key?: string;
  price: number;
  currency?: string;
  condition_label?: string;
  condition_notes?: string;
  description?: string;
  ships_from?: string;
  shipping_cost?: number;
  /** Opt in to this listing's photo being reused as catalogue art for the same
   *  product (ToS §3). Default false — never send true unless the seller
   *  actually ticked it. Revocable. */
  photo_catalogue_consent?: boolean;
}) => post<P2PListing>('/p2p/listings', payload);

/** Browse active member listings. `canonical_key` powers "other members
 *  selling this" on a catalog item page. */
export type P2PSort = 'newest' | 'price_asc' | 'price_desc';

export const listListings = (params?: {
  /** One slug, or several — several are OR'd server-side. Accepts a bare
   *  string so existing single-category callers are unchanged. */
  category?: string | string[];
  canonical_key?: string;
  /** Title search, server-side. Filtering titles on the client only searches
   *  the pages already downloaded, which stops being correct as soon as the
   *  list pages. */
  q?: string;
  mine?: boolean;
  /** Server-side. Client-side sorting would only reorder the loaded page,
   *  which looks correct until the result set exceeds one page and then
   *  quietly isn't. */
  sort?: P2PSort;
  /** Inclusive price bounds, server-side for the same reason as `sort`.
   *  Expressed in `price_currency`; the server converts them and compares
   *  against a EUR-normalised price, because sellers list in their own
   *  currency and comparing raw amounts across currencies is meaningless. */
  price_min?: number;
  price_max?: number;
  /** Currency the bounds are in. Defaults to EUR server-side; pass the user's
   *  display currency whenever the bounds came from something they typed. */
  price_currency?: string;
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams();
  // `append`, not `set` — repeated params are how the server receives a list,
  // and `set` would overwrite each previous one and silently send only the last.
  if (params?.category) {
    for (const c of Array.isArray(params.category) ? params.category : [params.category]) {
      if (c) q.append('category', c);
    }
  }
  if (params?.canonical_key) q.set('canonical_key', params.canonical_key);
  if (params?.q?.trim()) q.set('q', params.q.trim());
  if (params?.mine) q.set('mine', 'true');
  if (params?.sort) q.set('sort', params.sort);
  // `!= null`, not truthiness — a 0 lower bound is a legitimate filter.
  if (params?.price_min != null) q.set('price_min', String(params.price_min));
  if (params?.price_max != null) q.set('price_max', String(params.price_max));
  if (params?.price_currency) q.set('price_currency', params.price_currency);
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  const qs = q.toString();
  return get<{ listings: P2PListing[] }>(`/p2p/listings${qs ? `?${qs}` : ''}`);
};

export type P2PCategoryFacet = { category: string; count: number };

/**
 * Categories that actually have live listings, with counts.
 *
 * Offering all 54 app categories as filters meant most of them guaranteed an
 * empty grid. Counts are of live listings per category and ignore the caller's
 * other filters, so a category showing "3" can still return nothing under a
 * tight price cap.
 */
export const listCategoryFacets = () =>
  get<{ facets: P2PCategoryFacet[] }>('/p2p/facets/categories');

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
/**
 * Change the asking price on your own live listing.
 *
 * Dropping the price is the point: the server re-points the listing's buyable
 * `market_hits` row at the new figure and refreshes its `seen_at`, which puts it
 * back inside `deal_discovery_worker`'s 30-minute window. Every member whose
 * watchlist TARGET the new price now meets gets a Target Hit — not everyone who
 * favourited, only the people for whom it is actually news.
 *
 * Raising the price updates the listing but deliberately does NOT re-enter that
 * window: "listed below your target" is the promise, and an item getting more
 * expensive is a notification with no action.
 *
 * 404 covers not-yours / gone / already sold, deliberately undistinguished.
 * Re-saving the SAME price is a 200 no-op, not an error.
 */
export const updateListingPrice = (listingId: string, price: number) =>
  patch<P2PListing>(`/p2p/listings/${encodeURIComponent(listingId)}`, { price });

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
  /** Shipment visibility. DISPLAY ONLY — nothing may derive completion from
   *  it. Two-sided confirmation stays the only completion signal; auto-
   *  completing on a carrier's "delivered" would substitute our judgment for
   *  the buyer's and we would own the empty box. See P2P spec §5b. */
  tracking_carrier: string | null;
  /** Human label ("PostNL"), not the key ("postnl"). */
  tracking_carrier_label: string | null;
  tracking_code: string | null;
  tracking_set_at: string | null;
  /** The CARRIER's own tracking page, resolved server-side. Null when the
   *  carrier needs something we deliberately don't hold — PostNL and DPD both
   *  require the recipient's postcode — so render a copyable code, never a
   *  button that 404s. */
  tracking_url: string | null;
  i_am_buyer: boolean;
  /** Server-computed so the client never re-derives the state machine. */
  can_confirm: boolean;
  can_grade: boolean;
  already_graded: boolean;
  /** Seller-only, and only while the trade is live. A UI hint — the server
   *  enforces it independently. */
  can_add_tracking: boolean;
};

export type P2PCarrier = {
  key: string;
  label: string;
  /** False => no code-only tracking URL exists, so show a copyable code. */
  linkable: boolean;
};

/** Carriers the seller may pick. Served from the server's `_CARRIER_TRACKING`
 *  so the picker cannot drift from the URL table that resolves the link. */
export const listCarriers = () => get<P2PCarrier[]>('/p2p/carriers');

/**
 * Attach a shipment reference. Seller only, while `accepted` or `shipped`.
 *
 * Separate from `confirmExchange` on purpose: a mistyped code must be fixable
 * without re-running the completion state machine, and if one call fails the
 * seller retries only that one.
 */
export const setOfferTracking = (
  offerId: string,
  tracking_carrier: string,
  tracking_code: string,
) =>
  post<P2POffer>(`/p2p/offers/${encodeURIComponent(offerId)}/tracking`, {
    tracking_carrier,
    tracking_code,
  });

export const createOffer = (payload: {
  listing_id: string;
  amount: number;
  currency?: string;
  message?: string;
}) => post<P2POffer>('/p2p/offers', payload);

export const listOffers = (role: 'all' | 'buying' | 'selling' = 'all') =>
  get<{ offers: P2POffer[] }>(`/p2p/offers?role=${role}`);

/**
 * Does this offer need something from ME right now?
 *
 * Drives the marketplace badge, and is defined here rather than in a screen so
 * the badge count and any list that highlights the same rows cannot drift apart.
 *
 * `can_confirm` / `can_grade` are computed SERVER-side (see app/offers.tsx) —
 * the state machine is not re-derived on the client. The two status checks are
 * about whose turn it is to reply: a `pending` offer waits on the SELLER, and a
 * `countered` one waits on the BUYER. Counting both regardless of side would
 * badge a seller for their own outstanding counter-offer, i.e. nag them about
 * waiting for someone else.
 */
export function offerNeedsMyAction(o: P2POffer): boolean {
  if (o.can_confirm) return true;
  if (o.can_grade && !o.already_graded) return true;
  if (o.status === 'pending') return !o.i_am_buyer;
  if (o.status === 'countered') return o.i_am_buyer;
  return false;
}

/** How many offers are waiting on the caller. */
export const countOffersNeedingAction = (offers: P2POffer[]): number =>
  offers.reduce((n, o) => (offerNeedsMyAction(o) ? n + 1 : n), 0);

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
