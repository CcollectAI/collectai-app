/**
 * Which `value_source` values rest on market data, in ONE place.
 *
 * Until 2026-10-06 this set existed three times (ValueSourceChip,
 * portfolioAnalytics, Home), each with a comment saying it "must match" the
 * others: agreement by comment. Adding `catalog_price` would have needed three
 * identical edits, and missing one silently re-labels part of the collection
 * as an estimate on one screen only.
 *
 * Server side, `public.item_value_v1` is the definition (docs/ARCHITECTURE.md
 * "value-sources"). The leaderboard keeps its OWN, narrower list on the server
 * on purpose: `catalog_price` may be listing prices up to a year old, so it
 * counts as market-derived here (it is not the member's guess) but never ranks
 * a member in public.
 */
import { dateLocale, DATE_SHORT } from '@/constants/dateFormats';
import { parseEventDate } from '@/lib/calendar';

export const MARKET_VALUE_SOURCES: ReadonlySet<string> = new Set([
  'catalog_daily',
  'catalog_model',
  'quick_scan',
  // Catalogue price, used when no model value exists and the item's market
  // data is from this year (migration 20261006_item_value_v1_catalog_price).
  'catalog_price',
]);

export function isMarketBacked(source?: string | null): boolean {
  return !!source && MARKET_VALUE_SOURCES.has(source);
}

/**
 * "18 Aug" for `value_as_of`, a bare YYYY-MM-DD. Parsed as LOCAL midnight via
 * parseEventDate (a bare date through `new Date()` is UTC midnight, the
 * day-off-by-one that check-bare-date-parse exists for), formatted in the
 * member's app language (check-date-locale). Null for a missing or unreadable
 * date, so the caller shows the label without a date rather than "Invalid Date".
 */
export function formatValueAsOf(asOf?: string | null): string | null {
  if (!asOf) return null;
  const d = parseEventDate(asOf);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(dateLocale(), DATE_SHORT);
}
