/**
 * The item card called price-index snapshots "recorded sales". These pin the
 * corrected vocabulary AND the market attribution, because the failure mode is
 * an OVERCLAIM: a line that states more than the data supports is the exact
 * defect docs/COLLECTOR_DEMAND.md §1 says the category is judged on.
 */
import {
  describeComps, compNoun, marketOf, providerNames, providerLabel,
} from '@/lib/compProvenance';

const S = (source: string, count = 10) => ({ source, count });

describe('compNoun — never call an observation a sale', () => {
  it('index providers give "price observations", NOT sales', () => {
    expect(compNoun([S('scryfall'), S('tcgplayer')], 24)).toBe('price observations');
  });
  it('singular form', () => {
    expect(compNoun([S('scryfall')], 1)).toBe('price observation');
  });
  it('only providers with REAL sale timestamps earn the word "sale"', () => {
    expect(compNoun([S('pricecharting')], 5)).toBe('recorded sales');
    expect(compNoun([S('sparrow_p2p')], 1)).toBe('recorded sale');
  });
  it('a MIX degrades to observations — one index row makes "sales" false', () => {
    expect(compNoun([S('pricecharting'), S('scryfall')], 9)).toBe('price observations');
  });
  it('unknown sources are observations, not sales', () => {
    expect(compNoun(null, 3)).toBe('price observations');
    expect(compNoun([S('ebay')], 3)).toBe('price observations');
  });
});

describe('marketOf — verified per importer, never guessed from the brand', () => {
  it('scryfall is EU: import_mtg reads eur/eur_foil, which Scryfall takes from Cardmarket', () => {
    expect(marketOf([S('scryfall')])).toBe('EU');
  });
  it('lorcast is EU: import_lorcana reads price_eur', () => {
    expect(marketOf([S('lorcast')])).toBe('EU');
  });
  it('tcgplayer is US: import_pokemon does to_eur(market_price, "USD")', () => {
    expect(marketOf([S('tcgplayer')])).toBe('US');
  });
  it('pricecharting is US', () => {
    expect(marketOf([S('pricecharting')])).toBe('US');
  });
  it('both markets together is "mixed" — the ~31% gap we average across', () => {
    expect(marketOf([S('tcgplayer'), S('cardmarket')])).toBe('mixed');
  });
  it('returns NULL rather than guessing when no provider is mapped', () => {
    // eBay depends on the marketplace ID per query, so it makes no claim.
    expect(marketOf([S('ebay')])).toBeNull();
    expect(marketOf([])).toBeNull();
    expect(marketOf(null)).toBeNull();
  });
});

describe('providerNames', () => {
  it('orders by count, most-used first', () => {
    expect(providerNames([S('cardmarket', 3), S('scryfall', 40), S('tcgplayer', 12)]))
      .toEqual(['Scryfall', 'TCGplayer', 'Cardmarket']);
  });
  it('falls back to a capitalised raw name rather than dropping a source', () => {
    expect(providerLabel('acme_market')).toBe('Acme_market');
  });
});

describe('describeComps — every clause must be earned', () => {
  it('states count, providers and market', () => {
    expect(describeComps([S('tcgplayer', 12), S('cardmarket', 12)], 24))
      .toBe('Based on 24 price observations · TCGplayer, Cardmarket · US + EU markets');
  });
  it('names a single market when only one is present', () => {
    expect(describeComps([S('scryfall', 20)], 20))
      .toBe('Based on 20 price observations · Scryfall · EU market');
  });
  it('OMITS the market clause when no provider is mapped', () => {
    expect(describeComps([S('ebay', 4)], 4)).toBe('Based on 4 price observations · eBay');
  });
  it('omits the provider clause when sources are absent', () => {
    expect(describeComps(null, 7)).toBe('Based on 7 price observations');
  });
  it('flags below the reliability floor (_MIN_COMPS_RELIABLE = 3)', () => {
    expect(describeComps([S('scryfall', 2)], 2)).toContain('treat as an early estimate');
    expect(describeComps([S('scryfall', 3)], 3)).not.toContain('early estimate');
  });
  it('zero says there is no market data — never "based on 0"', () => {
    expect(describeComps([], 0)).toBe('No market data behind this yet');
  });
  it('null total renders nothing at all', () => {
    expect(describeComps([S('scryfall')], null)).toBeNull();
    expect(describeComps([S('scryfall')], undefined)).toBeNull();
  });
});
