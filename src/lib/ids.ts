/**
 * Identifier discrimination for route targets.
 *
 * `app/item/[id].tsx` is keyed by `items.id`, a Postgres **uuid**. Several
 * producers hand the app a *catalog key* instead (`pokemon:base1-base1-99`,
 * `watchlist_snipe:<uuid>`) because the columns that carry them are `text`:
 *
 *   - `alert_trigger_history.item_id`  (written from `price_predictions.item_ref`)
 *   - `catalog_suggestions.mapped_item_key`
 *   - push payload `data.item_id`
 *
 * Pushing one of those into `/item/[id]` makes PostgREST reject the query with
 * `22P02 invalid input syntax for type uuid`. Every call site swallows that as a
 * `logger.warn`, so the user gets an "Unknown item" shell and nothing goes red.
 * Verified against production 2026-07-25: 58/58 non-null `alert_trigger_history`
 * rows were catalog keys, 0 were uuid-shaped.
 *
 * Route through `itemHref()` rather than interpolating an id into a path, so a
 * catalog key lands on `/catalog-item/[key]` — the screen that is actually keyed
 * by the catalog item_key — instead of a dead uuid lookup.
 */

import type { Href } from 'expo-router';

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** True when `value` is a canonical 8-4-4-4-12 uuid (the shape `items.id` has). */
export function isUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_RE.test(value);
}

/**
 * Route target for "open this item", chosen by the shape of the identifier.
 *
 * uuid        -> `/item/[id]`         (a row in `items`, owned by the user)
 * anything    -> `/catalog-item/[key]` (a catalog entry; not user-owned)
 * empty/null  -> `null`, so callers can render the row as non-tappable
 *
 * `extras` are forwarded as route params — pass what you already have (title,
 * category) so the destination can render immediately instead of flashing
 * "Unknown item" while it fetches.
 */
export function itemHref(
  id: string | null | undefined,
  extras?: Record<string, string | undefined>,
): Href | null {
  if (typeof id !== 'string' || id.trim() === '') return null;

  const params: Record<string, string> = {};
  for (const [k, v] of Object.entries(extras ?? {})) {
    if (typeof v === 'string' && v !== '') params[k] = v;
  }

  if (isUuid(id)) {
    return { pathname: '/item/[id]', params: { ...params, id } } as Href;
  }
  return {
    pathname: '/catalog-item/[key]',
    params: { ...params, key: id },
  } as Href;
}

/**
 * OUR OWN marketplace listing URLs, so a Target Hit on a member listing opens
 * the app instead of a browser.
 *
 * `_publish_supply_hook` writes `https://sparrowcollect.com/l/<uuid>` into
 * `market_hits.url`, which is correct — it has to be an https link so it also
 * works when a seller shares it outside the app, and `build_affiliate_url`
 * rejects `sparrow://` outright.
 *
 * But both consumers of that column treat any https URL as external:
 *
 *   - `app/alerts.tsx`        -> `Linking.openURL(url)`
 *   - `app/notifications.tsx` -> `openAffiliateUrl(deep_link)`
 *
 * So the one alert the whole marketplace exists to produce (spec §1) bounced
 * the user out to a web page that returns **404** — there is no web listing
 * page, `/l` was not in the Android intent filters, and no `app/l/` route
 * existed. Sending someone to a browser to view something inside the app they
 * are already holding is bad; sending them to a 404 is the feature being dead.
 *
 * Returns null for every other URL, so callers keep their existing external
 * behaviour for eBay, Cardmarket and the rest by simply falling through. That
 * is the point of returning a route rather than a boolean: there is one place
 * that knows what our own links look like, and adding a second link shape later
 * means editing this function, not hunting call sites.
 */
const SPARROW_LISTING_RE =
  /^https?:\/\/(?:www\.)?sparrowcollect\.com\/l\/([0-9a-f-]{36})\/?$/i;

export function inAppListingHref(url: string | null | undefined): Href | null {
  if (typeof url !== 'string') return null;
  const m = SPARROW_LISTING_RE.exec(url.trim());
  // The captured group is loosely matched by the regex ([0-9a-f-]{36}), then
  // checked properly here — a shape check in the pattern would silently accept
  // 36 hyphens, and routing garbage into /listing/[id] is a 22P02 on the
  // server, which is exactly the failure this module was written for.
  if (!m || !isUuid(m[1])) return null;
  return { pathname: '/listing/[id]', params: { id: m[1] } } as Href;
}
