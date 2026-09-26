import { formatPrice, setActiveDisplayCurrency } from '@/lib/format';
import type { Settings } from '@/lib/settings';

// 2026-09-26: `formatPrice(x)` with no currency printed EUR to every member —
// the chart said "€1.253" under a "$1.429" header. An omitted currency now
// means "EUR amount, in the member's currency"; an explicit one is as given.
const usd = { currency: 'USD', fxRates: { USD: 1.14 } } as unknown as Pick<Settings, 'currency' | 'fxRates'>;

afterEach(() => setActiveDisplayCurrency(null));

describe('formatPrice display-currency chokepoint', () => {
  it('converts an EUR amount when no currency is given', () => {
    setActiveDisplayCurrency(usd);
    expect(formatPrice(100)).toMatch(/^\$114$/);
  });

  it('formats an explicit currency as given — no conversion', () => {
    setActiveDisplayCurrency(usd);
    expect(formatPrice(100, 'EUR')).toMatch(/^€100$/);
    expect(formatPrice(100, 'USD')).toMatch(/^\$100$/);
  });

  it('keeps EUR when no display currency is known (tests, pre-mount)', () => {
    expect(formatPrice(100)).toMatch(/^€100$/);
  });
});
