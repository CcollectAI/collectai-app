import { portfolioTotalLabel } from '../../src/lib/portfolioTotalLabel';

// EUR → USD at 1.10, so a conversion bug is visible in the digits, not just the symbol.
const usd = { currency: 'USD' as const, numberLocale: 'en-US' as const, fxRates: { USD: 1.1 } as Record<string, number> };
const eur = { currency: 'EUR' as const, numberLocale: 'de-DE' as const, fxRates: {} as Record<string, number> };

describe('portfolioTotalLabel', () => {
  it('uses the SERVER total, not the loaded rows (Items must agree with Home)', () => {
    // 20 of 50 items loaded: the rows sum to 400, the collection is worth 1000.
    expect(portfolioTotalLabel(1000, 400, true, eur)).toContain('1.000');
    expect(portfolioTotalLabel(1000, 400, true, eur)).not.toContain('400');
  });

  it('marks a partial number with + when the server total is missing', () => {
    expect(portfolioTotalLabel(null, 400, true, eur)).toMatch(/\+$/);
  });

  it('does not mark it + once every page is loaded', () => {
    expect(portfolioTotalLabel(null, 400, false, eur)).not.toMatch(/\+$/);
  });

  it('treats a server total of 0 as an answer, not as missing', () => {
    expect(portfolioTotalLabel(0, 400, true, eur)).not.toContain('400');
  });

  it('CONVERTS into the member currency (EUR amount must not be printed under $)', () => {
    const label = portfolioTotalLabel(1000, 0, false, usd);
    expect(label).toContain('$');
    expect(label).toContain('1,100'); // 1000 EUR at 1.10 — not 1,000
  });
});
