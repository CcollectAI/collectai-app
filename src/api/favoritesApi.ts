/**
 * Favorites API client — "saved", and nothing more.
 *
 * Mirrors server/app/features/favorites_router.py.
 *
 * READ THIS BEFORE WIRING A HEART ANYWHERE. Favouriting is NOT watching, and
 * the difference is not cosmetic:
 *
 *   heart → `favoritesApi`      saved. No target price, no alert, no plan gate.
 *   eye   → `addWatchlistItem`  a target price and a Target Hit alert.
 *
 * A heart wired to `addWatchlistItem` was built on the marketplace grid
 * 2026-08-08 and removed the same day: it wrote rows with no `targetPrice`, and
 * `_check_watchlist_snipes` filters `WHERE target_price IS NOT NULL AND > 0`, so
 * every row it produced was inert while its own accessibility label promised
 * price-drop alerts. docs/alerts-and-insights.md records it as the fourth
 * instance of that writer bug. Two verbs, two stores, neither one lying.
 *
 * snake_case crosses the wire verbatim, matching p2pApi.
 */
import { get, post, del } from './httpClient';

export type Favorite = {
  id: string;
  /** Set when the favourite points at a marketplace listing. Mutually
   *  exclusive with canonical_key — the DB enforces it
   *  (`favorites_one_target`). */
  listing_id: string | null;
  /** Set when it points at a catalogue item. BARE, never namespaced. */
  canonical_key: string | null;
  /** Slug ('mtg'), never a display name. */
  category: string | null;
  created_at: string | null;

  /** Denormalised for rendering. All nullable ON PURPOSE: a listing the seller
   *  has since delisted keeps its favourite row, and the screen renders a
   *  "no longer available" state rather than dropping something the member
   *  explicitly saved. Do not filter these out. */
  title: string | null;
  price: number | null;
  currency: string | null;
  image_url: string | null;
  listing_status: string | null;
};

/** Exactly one of these is set — mirrors the server's `_exactly_one_target`
 *  validator and the DB CHECK. */
export type FavoriteTarget =
  | { listing_id: string; canonical_key?: never }
  | { canonical_key: string; listing_id?: never };

/** Everything this member saved, newest first. */
export async function listFavorites(limit = 100, offset = 0): Promise<Favorite[]> {
  return get<Favorite[]>(`/favorites?limit=${limit}&offset=${offset}`);
}

/**
 * The set of favourited targets, for filling in hearts on a grid.
 *
 * Returns listing ids and canonical keys in ONE flat list — which is safe only
 * because a uuid can never collide with a canonical key. The card asks "is my
 * id in this set?" without needing to know which kind it holds.
 */
export async function fetchFavoriteIds(): Promise<Set<string>> {
  const ids = await get<string[]>('/favorites/ids');
  return new Set(ids);
}

/** Save it. Idempotent — the server upserts, so a double-tap is not an error. */
export async function addFavorite(
  target: FavoriteTarget,
  category?: string | null,
): Promise<Favorite> {
  return post<Favorite>('/favorites', {
    listing_id: target.listing_id ?? null,
    canonical_key: target.canonical_key ?? null,
    // Slug. If you are passing something a user could read, it is wrong.
    category: category ?? null,
  });
}

/** Un-save it, addressed by target rather than by row id — the card knows what
 *  it is looking at, not the id of a favorites row it never fetched. */
export async function removeFavorite(target: FavoriteTarget): Promise<void> {
  const q = target.listing_id
    ? `listing_id=${encodeURIComponent(target.listing_id)}`
    : `canonical_key=${encodeURIComponent(target.canonical_key!)}`;
  await del<void>(`/favorites?${q}`);
}
