/**
 * `filterImplausibleHits` — the guard between a scraping adapter and a paying
 * member's screen.
 *
 * The case that created it: a crawl4ai row titled "Site Statistics" rendered
 * at EUR 1,620,277,371 in the item screen's "Market Prices" section, on Pro.
 * The display path had no bound of any kind.
 */
import {
  filterImplausibleHits,
  MAX_SANE_PRICE,
  MAX_MULTIPLE_OF_VALUATION,
} from '@/lib/marketHitSanity';

const hit = (price: number | null | undefined) => ({ price });

describe('filterImplausibleHits', () => {
  it('drops the reported EUR 1.62bn page-counter row', () => {
    const r = filterImplausibleHits([hit(1_620_277_371), hit(42)], 50);
    expect(r.kept).toEqual([hit(42)]);
    expect(r.dropped).toBe(1);
  });

  it('drops non-positive and unparseable prices', () => {
    const r = filterImplausibleHits([hit(0), hit(-5), hit(NaN), hit(null), hit(undefined), hit(10)]);
    expect(r.kept).toEqual([hit(10)]);
    expect(r.dropped).toBe(5);
  });

  it('applies the absolute bound even with NO valuation reference', () => {
    // An unpriced item still must not be shown a billion-euro comp.
    const r = filterImplausibleHits([hit(MAX_SANE_PRICE + 1), hit(MAX_SANE_PRICE)], null);
    expect(r.kept).toEqual([hit(MAX_SANE_PRICE)]);
  });

  it('does NOT empty the list for an unpriced item', () => {
    // The reference is what is missing, not the rows. Regression guard: an
    // early version that treated a null valuation as 0 would drop everything.
    const r = filterImplausibleHits([hit(10), hit(20), hit(30)], null);
    expect(r.kept).toHaveLength(3);
    expect(r.dropped).toBe(0);
  });

  it('keeps a WIDE but real spread around the valuation', () => {
    // A 10x comp is a wide market, not junk. Hiding it is the worse failure.
    const r = filterImplausibleHits([hit(500), hit(5)], 50);
    expect(r.kept).toHaveLength(2);
  });

  it('drops only beyond the loose multiple of the valuation', () => {
    const ref = 50;
    const justInside = ref * MAX_MULTIPLE_OF_VALUATION;
    const r = filterImplausibleHits([hit(justInside), hit(justInside + 1)], ref);
    expect(r.kept).toEqual([hit(justInside)]);
  });
});

/**
 * Relevance, tested against the ACTUAL rows from the reported screenshot
 * (IMG_3924): a Japanese vinyl item whose "Market Prices" section listed five
 * suruga_ya products, three of which were entirely different records.
 */
import { filterComps, isPlausibleListing, significantTokens } from '@/lib/marketHitSanity';

// The item, and the five titles as they appeared.
const ITEM = 'ウッドストック 愛と平和と音楽の3日間 40周年';
const ROWS = [
  { title: 'SONIC LOST WORLD ORIGINAL SOUNDTRACK', price: 28 },        // different record
  { title: 'ディレクターズカット ウッドストック 愛と平和と音楽の3日間 40周年', price: 22 }, // same film, director's cut
  { title: '南佳孝 / ラジオな曲たち2', price: 20 },                      // different record
  { title: 'BLACK BOTTOM BRASS BAND / ワッショイ', price: 19 },          // different record
  { title: 'ウッドストック 愛と平和と音楽の3日間 40周年', price: 11 },      // the item
];

describe('relevance (the reported vinyl screen)', () => {
  it('tokenises a Japanese title at all — the server rule would return NOTHING', () => {
    // `[^a-z0-9]+` yields [] here, and the server then rejects every listing.
    expect(ITEM.toLowerCase().match(/[a-z0-9]+/g)?.filter((t) => t.length >= 3) ?? []).toHaveLength(0);
    expect(significantTokens(ITEM).length).toBeGreaterThan(0);
  });

  it('keeps the two rows that ARE this record and drops the three that are not', () => {
    const r = filterComps(ROWS, ITEM, 8015);
    expect(r.kept.map((h) => h.price).sort((a, b) => a - b)).toEqual([11, 22]);
    expect(r.droppedIrrelevant).toBe(3);
    expect(r.droppedImplausiblePrice).toBe(0);
  });

  it('separates the two reasons a row can be dropped', () => {
    const withJunk = [...ROWS, { title: ITEM, price: 1_620_277_371 }];
    const r = filterComps(withJunk, ITEM, 8015);
    expect(r.droppedImplausiblePrice).toBe(1); // the page counter
    expect(r.droppedIrrelevant).toBe(3);       // the other records
  });

  it('rejects accessories that carry the item name', () => {
    expect(isPlausibleListing('MTG Card Sleeves - Bayou', 'Bayou')).toBe(false);
    expect(isPlausibleListing('Bayou MTG Magic the Gathering card', 'Bayou')).toBe(true);
  });

  it('returns NOTHING rather than guessing when the item has no usable title', () => {
    expect(filterComps(ROWS, '', 8015).kept).toHaveLength(0);
  });
});
