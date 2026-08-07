/**
 * Query-string construction for the marketplace browse call.
 *
 * Why this file exists: the filter sheet is multi-select, and `category` used to
 * be a single string. Selecting three categories kept one and dropped two with
 * no error anywhere — the sheet even reopened showing only the survivor, so the
 * UI agreed with itself. The fix is repeated `category` params OR'd server-side,
 * and the failure mode is subtle: `q.set()` instead of `q.append()` overwrites
 * each previous value and silently sends only the LAST one. That reads as
 * "the filter works" in every single-category test.
 *
 * These assert the URL, because the URL is the contract with
 * server/app/features/p2p_listing_router.py::browse_listings.
 */

import { listListings } from '@/api/p2pApi';

const mockGet = jest.fn();

jest.mock('@/api/httpClient', () => ({
  get: (path: string) => mockGet(path),
  post: jest.fn(),
}));

/** The path listListings handed to httpClient. */
const calledPath = () => mockGet.mock.calls[0][0] as string;
const paramsOf = (path: string) => new URLSearchParams(path.split('?')[1] ?? '');

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockResolvedValue({ listings: [] });
});

describe('listListings query string', () => {
  it('sends no query at all when given nothing', () => {
    listListings();
    expect(calledPath()).toBe('/p2p/listings');
  });

  it('sends a single category as one param', () => {
    listListings({ category: 'pokemon' });
    expect(paramsOf(calledPath()).getAll('category')).toEqual(['pokemon']);
  });

  it('REPEATS the param for several categories rather than overwriting', () => {
    listListings({ category: ['pokemon', 'lego', 'comics'] });
    // getAll, not get — `get` returns the first and would pass even if the
    // other two had been clobbered.
    expect(paramsOf(calledPath()).getAll('category')).toEqual([
      'pokemon',
      'lego',
      'comics',
    ]);
  });

  it('drops empty category strings instead of sending category=', () => {
    listListings({ category: ['pokemon', ''] });
    expect(paramsOf(calledPath()).getAll('category')).toEqual(['pokemon']);
  });

  it('omits category entirely for an empty array', () => {
    listListings({ category: [] });
    expect(paramsOf(calledPath()).has('category')).toBe(false);
  });

  it('sends price bounds with the currency they are expressed in', () => {
    listListings({ price_min: 10, price_max: 100, price_currency: 'JPY' });
    const p = paramsOf(calledPath());
    expect(p.get('price_min')).toBe('10');
    expect(p.get('price_max')).toBe('100');
    expect(p.get('price_currency')).toBe('JPY');
  });

  it('sends a zero lower bound — 0 is a real filter, not "unset"', () => {
    // A truthiness check here would drop it and quietly widen the search.
    listListings({ price_min: 0 });
    expect(paramsOf(calledPath()).get('price_min')).toBe('0');
  });

  it('omits price bounds that were not supplied', () => {
    listListings({ sort: 'price_asc' });
    const p = paramsOf(calledPath());
    expect(p.has('price_min')).toBe(false);
    expect(p.has('price_max')).toBe(false);
    expect(p.get('sort')).toBe('price_asc');
  });

  it('sends the search term server-side, trimmed', () => {
    // Server-side because a client-side title filter only searches the pages
    // already downloaded — which silently under-reports once the list pages.
    listListings({ q: '  charizard  ' });
    expect(paramsOf(calledPath()).get('q')).toBe('charizard');
  });

  it('omits a blank search rather than sending q=', () => {
    listListings({ q: '   ' });
    expect(paramsOf(calledPath()).has('q')).toBe(false);
  });

  it('sends limit and offset so pages do not overlap', () => {
    listListings({ limit: 24, offset: 48 });
    const p = paramsOf(calledPath());
    expect(p.get('limit')).toBe('24');
    expect(p.get('offset')).toBe('48');
  });

  it('sends offset=0 explicitly — the first page is a real offset', () => {
    listListings({ limit: 24, offset: 0 });
    expect(paramsOf(calledPath()).get('offset')).toBe('0');
  });

  it('carries mine and sort together', () => {
    listListings({ mine: true, sort: 'newest', category: ['lego'] });
    const p = paramsOf(calledPath());
    expect(p.get('mine')).toBe('true');
    expect(p.get('sort')).toBe('newest');
    expect(p.getAll('category')).toEqual(['lego']);
  });
});
