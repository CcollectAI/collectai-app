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
