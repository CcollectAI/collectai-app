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

import { browseCatalogItems } from '@/api/intakeApi';
import { cacheGet, cacheSet } from '@/data/offlineCache';
import logger from '@/utils/logger';

type BrowseOpts = Parameters<typeof browseCatalogItems>[1];
type BrowseResult = Awaited<ReturnType<typeof browseCatalogItems>>;

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
