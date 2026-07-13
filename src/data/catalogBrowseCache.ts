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

  if (cached !== null) {
    // Stale-while-revalidate: return the cached page now, refresh in the
    // background so the next mount has fresh prices.
    browseCatalogItems(categoryId, opts)
      .then((fresh) => cacheSet(cacheKey, fresh, TTL_MS))
      .catch((err) => logger.warn(`[catalogBrowseCache] bg revalidate ${cacheKey}:`, err));
    return cached;
  }

  const fresh = await browseCatalogItems(categoryId, opts);
  await cacheSet(cacheKey, fresh, TTL_MS);
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

  if (cached !== null) {
    getCatalogCollections(categoryId, limit, groupBy)
      .then((fresh) => cacheSet(cacheKey, fresh, TTL_MS))
      .catch((err) => logger.warn(`[catalogBrowseCache] bg revalidate ${cacheKey}:`, err));
    return cached;
  }

  const fresh = await getCatalogCollections(categoryId, limit, groupBy);
  await cacheSet(cacheKey, fresh, TTL_MS);
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
