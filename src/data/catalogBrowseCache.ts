/**
 * catalogBrowseCache — stale-while-revalidate wrapper around
 * collectorsApi.browseCatalogItems for the category carousels.
 *
 * Why: the category-page rails (CategoryOverviewRail ×2, NewReleasesSection)
 * and the museum "From this set" rail re-mount on every navigation and every
 * sort-chip toggle, and each one previously re-fetched from scratch behind a
 * skeleton — even for data shown seconds earlier. The backend is fast warm
 * (~0.15–0.23s) but cold first-hits spike to ~0.7–0.9s and device→eu-north-1
 * RTT stacks across the page, so the carousels *felt* slow on every revisit.
 *
 * Catalog rows only change nightly (mv_catalog_item_price refreshes 00:00 UTC),
 * so a 15-minute persistent TTL makes revisits/toggles instant while a
 * background revalidate keeps prices fresh. This mirrors the private swr()
 * helper in CachedDataProvider; it lives here because the rails call the API
 * layer directly instead of going through the DataProvider.
 *
 * offlineCache no-ops gracefully on web and on any SQLite error (returns null),
 * so a cache failure simply degrades to the existing direct-fetch behaviour.
 */

import { browseCatalogItems, getCatalogCollections } from '@/api/intakeApi';
import { cacheGet, cacheSet } from '@/data/offlineCache';
import logger from '@/utils/logger';

type BrowseOpts = Parameters<typeof browseCatalogItems>[1];
type BrowseResult = Awaited<ReturnType<typeof browseCatalogItems>>;
type CollectionsResult = Awaited<ReturnType<typeof getCatalogCollections>>;

// 15 min — matches the TTL_LONG "categories" tier in CachedDataProvider.
const TTL_MS = 15 * 60 * 1000;

/**
 * True when a browse/collections payload has no rows. We deliberately DON'T
 * cache or serve empty results: the backend can transiently return `[]` while
 * mv_category_top_value / mv_catalog_item_price refresh (00:00 & 03:10 UTC), on
 * a cold-start race, or after a brief 5xx. Caching that for 15 min pinned the
 * category rail to "No catalog items" even though the data existed (the full
 * grid, which fetches uncached, showed the same items fine). Treating empty as
 * a miss means a populated backend always wins on the very next fetch.
 */
function isEmptyResult(r: unknown): boolean {
  const rows = (r as { items?: unknown[]; collections?: unknown[] } | null)?.items
    ?? (r as { collections?: unknown[] } | null)?.collections;
  return !Array.isArray(rows) || rows.length === 0;
}

function keyFor(categoryId: string, opts?: BrowseOpts): string {
  return [
    'catalog:browse',
    categoryId,
    opts?.sort ?? 'title',
    opts?.pricedOnly ? 'priced' : 'all',
    opts?.limit ?? '',
    opts?.offset ?? '',
    opts?.rarity ?? '',
    opts?.q?.trim() ?? '',
    // set/brand scope the set-detail grid — MUST be in the key or two sets
    // with the same (category, sort, limit, offset) collide on one entry.
    opts?.setCode ?? '',
    opts?.brand ?? '',
  ].join(':');
}

/**
 * Drop-in cached replacement for collectorsApi.browseCatalogItems.
 * Returns cached data immediately when warm (and silently revalidates);
 * otherwise fetches and caches.
 */
export async function browseCatalogItemsCached(
  categoryId: string,
  opts?: BrowseOpts,
): Promise<BrowseResult> {
  const cacheKey = keyFor(categoryId, opts);
  const cached = await cacheGet<BrowseResult>(cacheKey);

  // Serve stale ONLY when it's non-empty. A cached empty is treated as a miss
  // so a populated backend recovers on this very visit (not a future mount).
  if (cached !== null && !isEmptyResult(cached)) {
    // Stale-while-revalidate: return the cached page now, refresh in the
    // background so the next mount has fresh prices.
    browseCatalogItems(categoryId, opts)
      .then((fresh) => { if (!isEmptyResult(fresh)) return cacheSet(cacheKey, fresh, TTL_MS); })
      .catch((err) => logger.warn(`[catalogBrowseCache] bg revalidate ${cacheKey}:`, err));
    return cached;
  }

  const fresh = await browseCatalogItems(categoryId, opts);
  // Only persist non-empty results — never let a transient [] stick for 15 min.
  if (!isEmptyResult(fresh)) await cacheSet(cacheKey, fresh, TTL_MS);
  return fresh;
}

/**
 * Drop-in cached replacement for collectorsApi.getCatalogCollections, used by
 * FeaturedCollectionsSection. Same rationale as browseCatalogItemsCached: the
 * collections endpoint is fast warm (~60ms) but cold first-hits spike to
 * 1.6–2.7s, and the carousel re-fetched on every category mount with no cache
 * behind a skeleton. Set_code/brand groupings only change with the nightly
 * catalog refresh, so the 15-min SWR TTL keeps revisits instant.
 */
export async function getCatalogCollectionsCached(
  categoryId: string,
  limit?: number,
  groupBy?: 'set' | 'brand',
): Promise<CollectionsResult> {
  const cacheKey = ['catalog:collections', categoryId, groupBy ?? 'set', limit ?? ''].join(':');
  const cached = await cacheGet<CollectionsResult>(cacheKey);

  // Same empty-is-a-miss rule as browseCatalogItemsCached (Browse by Set).
  if (cached !== null && !isEmptyResult(cached)) {
    getCatalogCollections(categoryId, limit, groupBy)
      .then((fresh) => { if (!isEmptyResult(fresh)) return cacheSet(cacheKey, fresh, TTL_MS); })
      .catch((err) => logger.warn(`[catalogBrowseCache] bg revalidate ${cacheKey}:`, err));
    return cached;
  }

  const fresh = await getCatalogCollections(categoryId, limit, groupBy);
  if (!isEmptyResult(fresh)) await cacheSet(cacheKey, fresh, TTL_MS);
  return fresh;
}

/**
 * Page size for the set-detail grid's first page. Single source of truth so the
 * prefetch below and the grid screen (app/catalog-set/[setCode].tsx) produce the
 * SAME cache key — a mismatch would silently waste the prefetch.
 */
export const SET_GRID_PAGE_SIZE = 60;

/**
 * Warm the set-detail grid's first page into the cache. Called on press-in of a
 * collection tile so the grid is already cached by the time the screen mounts —
 * the first tap feels instant, not just revisits. Fire-and-forget; mirrors the
 * grid's exact first-page fetch (offset 0, sort 'set', set/brand by dimension).
 */
export function prefetchSetGridFirstPage(
  categoryId: string,
  groupBy: 'set' | 'brand' | undefined,
  collectionKey: string,
): void {
  const scope = groupBy === 'brand' ? { brand: collectionKey } : { setCode: collectionKey };
  void browseCatalogItemsCached(categoryId, {
    ...scope,
    limit: SET_GRID_PAGE_SIZE,
    offset: 0,
    sort: 'set',
  }).catch(() => {
    /* prefetch is best-effort; the grid screen will fetch normally on mount */
  });
}
