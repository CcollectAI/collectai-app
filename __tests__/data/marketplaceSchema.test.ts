/**
 * MarketplaceHitSchema — affiliate + resilience gate.
 *
 * The marketplace search response is the ONLY surface where a user opens an
 * outbound marketplace link in bulk, so it is where affiliate attribution
 * actually earns. The backend tags every hit (marketplace_router.py:133 sets
 * `affiliate_url`), but this schema did not declare that field and had no
 * `.passthrough()`, so Zod stripped it during safeParse. The screen then read
 * `h.affiliate_url ?? undefined` (marketplace.tsx:426) and always got
 * undefined, so `affiliateUrl || externalUrl` (marketplace.tsx:527) always
 * opened the UNTAGGED url — every search result earned nothing.
 *
 * Second failure mode pinned here: the hit fields were non-nullable, and a
 * single malformed hit fails the whole `z.array(...)`, which fails the whole
 * response, which drops safeParse to the `{results: [], hits: []}` fallback —
 * turning one bad row into an empty search page.
 */
import {
  MarketplaceSearchResponseSchema,
  MarketplaceHitSchema,
} from '../../src/api/schemas';

const goodHit = {
  source: 'ebay',
  title: 'Charizard Base Set',
  price: 120.5,
  currency: 'EUR',
  url: 'https://www.ebay.com/itm/1',
  affiliate_url: 'https://www.ebay.com/itm/1?campid=5338&mkevt=1',
};

describe('MarketplaceHitSchema — affiliate pass-through', () => {
  it('preserves affiliate_url so the tagged link survives parsing', () => {
    const parsed = MarketplaceHitSchema.parse(goodHit) as Record<string, unknown>;
    expect(parsed.affiliate_url).toBe(goodHit.affiliate_url);
  });

  it('preserves affiliate_url through the full response parse', () => {
    const res = MarketplaceSearchResponseSchema.parse({ hits: [goodHit] });
    expect(res.hits?.[0]).toBeDefined();
    expect((res.hits![0] as Record<string, unknown>).affiliate_url).toBe(goodHit.affiliate_url);
  });

  it('keeps an untagged hit parseable (affiliate_url may be null)', () => {
    const res = MarketplaceSearchResponseSchema.parse({
      hits: [{ ...goodHit, affiliate_url: null }],
    });
    expect(res.hits).toHaveLength(1);
  });
});

describe('MarketplaceHitSchema — one bad row must not empty the page', () => {
  it('tolerates a zero price without failing the whole array', () => {
    const res = MarketplaceSearchResponseSchema.parse({
      hits: [goodHit, { ...goodHit, price: 0 }],
    });
    expect(res.hits).toHaveLength(2);
  });

  it('tolerates a null price', () => {
    const res = MarketplaceSearchResponseSchema.parse({
      hits: [{ ...goodHit, price: null }],
    });
    expect(res.hits).toHaveLength(1);
  });

  it('tolerates a missing title/source rather than dropping every result', () => {
    const res = MarketplaceSearchResponseSchema.parse({
      hits: [{ ...goodHit, title: null }, { ...goodHit, source: null }],
    });
    expect(res.hits).toHaveLength(2);
  });
});
