/**
 * Says WHAT our price figure is made of: how many observations, from which
 * providers, and from which market.
 *
 * WHY THIS EXISTS (2026-08-30)
 *
 * docs/COLLECTOR_DEMAND.md §1: the loudest complaint about every collection
 * app is that a total is "a number without a question attached". One identical
 * 25-card collection priced four legitimate ways spans 60%, and no app says
 * which of the four it used.
 *
 * Two things were wrong on our side, both verified on prod before this was
 * written:
 *
 * 1. **We called them sales, and they are not.** 99.98% of the rows feeding a
 *    valuation carry neither `ended_at` nor a source sale time — they are daily
 *    price-index observations from Scryfall (48.6%), TCGplayer (28.6%) and
 *    Cardmarket (21.9%), roughly 49 / 28 / 22 rows per card. Only ~814
 *    pricecharting rows are real completed sales. The item card said "Based on
 *    N recorded sales" and the explanation sheet said "N comparable sales".
 *    Both were false, on the screen whose whole job is to be trustworthy.
 * 2. **We erase the market of origin at ingest.** TCGplayer prices are US
 *    market, converted USD->EUR by `to_eur()` and stored with `currency='EUR'`,
 *    so the currency column cannot tell EU from US. Research puts those two
 *    markets ~31% apart, and we average across them silently. `provider` is the
 *    only surviving signal, which is why the map below keys on it.
 *
 * No migration was needed for either: `_build_evidence` in valuation_worker
 * already returns `{source, count, avg_price, date_range}` per provider plus
 * `total_comps`, and the FE already receives it.
 */

/** Display names. Mirrors `_SOURCE_NAMES` in server/workers/valuation_worker.py. */
const PROVIDER_LABEL: Record<string, string> = {
  scryfall: 'Scryfall',
  tcgplayer: 'TCGplayer',
  cardmarket: 'Cardmarket',
  lorcast: 'Lorcast',
  pricecharting: 'PriceCharting',
  ebay: 'eBay',
  discogs: 'Discogs',
  suruga_ya: 'Suruga-ya',
  crawl4ai: 'Web',
  sparrow_p2p: 'Sparrow members',
};

export type Market = 'EU' | 'US' | 'mixed';

/**
 * Which market a provider's prices describe. Each verified in the importer
 * rather than assumed from the brand:
 *   - scryfall  -> import_mtg.py reads `eur`/`eur_foil`, which Scryfall sources
 *                  from Cardmarket. EU, despite Scryfall being a US site.
 *   - lorcast   -> import_lorcana.py reads `price_eur`/`price_eur_foil`. EU.
 *   - tcgplayer -> import_pokemon.py `to_eur(market_price, 'USD')`. US.
 *   - pricecharting -> adapter sets currency 'USD'. US.
 * A provider absent from this map contributes no market claim at all, which is
 * the honest default -- eBay depends on the marketplace ID per query.
 */
const PROVIDER_MARKET: Record<string, Market> = {
  scryfall: 'EU',
  cardmarket: 'EU',
  lorcast: 'EU',
  tcgplayer: 'US',
  pricecharting: 'US',
};

/**
 * Providers whose rows are genuinely COMPLETED SALES rather than price-index
 * observations. Deliberately tiny: a provider earns a place here only if its
 * rows carry a real sale timestamp.
 */
const SOLD_PROVIDERS = new Set(['pricecharting', 'sparrow_p2p']);

export type CompSourceLike = { source?: string | null; count?: number | null };

export function providerLabel(source?: string | null): string {
  if (!source) return 'Market data';
  return PROVIDER_LABEL[source] ?? source.charAt(0).toUpperCase() + source.slice(1);
}

/** Providers present, most-used first, as display names. */
export function providerNames(sources: CompSourceLike[] | null | undefined): string[] {
  if (!sources?.length) return [];
  return [...sources]
    .filter((s) => s?.source)
    .sort((a, b) => (b.count ?? 0) - (a.count ?? 0))
    .map((s) => providerLabel(s.source));
}

/**
 * Which market(s) the figure is drawn from, or null when we cannot say.
 * Returns null rather than guessing: an unknown market stated as EU would be
 * exactly the overclaim this module exists to stop.
 */
export function marketOf(sources: CompSourceLike[] | null | undefined): Market | null {
  if (!sources?.length) return null;
  const seen = new Set<Market>();
  for (const s of sources) {
    const m = s?.source ? PROVIDER_MARKET[s.source] : undefined;
    if (m) seen.add(m);
  }
  if (seen.size === 0) return null;
  if (seen.size > 1) return 'mixed';
  return [...seen][0];
}

/**
 * The noun for what we counted.
 *
 * Three tiers, and the middle one is the point. Verified 2026-08-31 by reading
 * the importers and each source's own documentation, rather than inferring from
 * the column names:
 *
 *   cardmarket  21.9%  `averageSellPrice` (→ avg30)  COMPLETED SALES average
 *   tcgplayer   28.6%  `market`                      TCGplayer Market Price,
 *                                                    computed from recent sales
 *   scryfall    48.6%  `eur` / `eur_foil`            Cardmarket TREND PRICE,
 *                                                    falling back to 1-day,
 *                                                    7-day, average, or
 *                                                    SUGGESTED price
 *   pricecharting        rows with a real `ended_at`  actual sales
 *
 * So "market prices" is the honest word for the bulk of it: sales-DERIVED, but
 * aggregated by the source and — for Scryfall's fallback — occasionally a
 * suggested figure. Not "completed sales", which we cannot evidence per row.
 * Not "observations" either, which is vaguer than the truth and was what this
 * said until today.
 *
 * "sales" stays reserved for providers whose rows carry an actual sale time.
 */
export function compNoun(sources: CompSourceLike[] | null | undefined, n: number): string {
  const allSold = !!sources?.length && sources.every((s) => s?.source && SOLD_PROVIDERS.has(s.source));
  if (allSold) return n === 1 ? 'recorded sale' : 'recorded sales';
  return n === 1 ? 'market price' : 'market prices';
}

/**
 * One muted line under the figure: how many, from whom, from where.
 *
 * Shape: "Based on 24 market prices · TCGplayer, Cardmarket · US + EU markets"
 * Every clause is dropped when it cannot be stated truthfully, so the line
 * degrades to just the count rather than inventing provenance.
 */
export function describeComps(
  sources: CompSourceLike[] | null | undefined,
  totalComps: number | null | undefined,
  minReliable = 3,
): string | null {
  if (totalComps == null) return null;
  if (totalComps === 0) return 'No market data behind this yet';

  const noun = compNoun(sources, totalComps);
  const parts = [`Based on ${totalComps} ${noun}`];

  const names = providerNames(sources);
  if (names.length) parts.push(names.slice(0, 3).join(', '));

  const market = marketOf(sources);
  if (market === 'mixed') parts.push('US + EU markets');
  else if (market) parts.push(`${market} market`);

  const line = parts.join(' · ');
  // Below the reliability floor the stored confidence is already capped
  // (_MIN_COMPS_RELIABLE). This is the same fact in words.
  return totalComps < minReliable ? `${line} — treat as an early estimate` : line;
}
