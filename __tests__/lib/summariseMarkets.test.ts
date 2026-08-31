/**
 * The portfolio total must say WHICH markets it rests on, or say nothing —
 * never default to one. EU and US price the same card ~31% apart
 * (docs/COLLECTOR_DEMAND.md §3) and we blend them.
 */
import { summariseMarkets } from '@/lib/portfolioAnalytics';

const comp = (market?: string) => ({ valueSource: 'catalog_daily', market });

describe('summariseMarkets', () => {
  it('names a single market', () => {
    expect(summariseMarkets([comp('EU'), comp('EU')]).label).toBe('EU market');
  });

  it('names both when both are present', () => {
    expect(summariseMarkets([comp('US'), comp('EU')]).label).toBe('EU + US markets');
  });

  it('a MIXED item alone still implies both markets', () => {
    expect(summariseMarkets([comp('mixed')]).label).toBe('EU + US markets');
  });

  it('renders NOTHING rather than guessing when no market is known', () => {
    // 84% of stored predictions predate the 2026-08-27 provider fix and say
    // 'unknown'. "EU market" by default would be the overclaim this exists to
    // avoid.
    expect(summariseMarkets([comp(undefined), comp(undefined)]).label).toBeNull();
    expect(summariseMarkets([]).label).toBeNull();
  });

  it('counts unknowns instead of folding them into a side', () => {
    const s = summariseMarkets([comp('US'), comp(undefined)]);
    expect(s.us).toBe(1);
    expect(s.unknownCount).toBe(1);
    expect(s.label).toBe('US market');
  });

  it('IGNORES estimate-backed items — an estimate has no provider', () => {
    // Counting a member's own guess as market data would invent provenance.
    const s = summariseMarkets([
      { valueSource: 'user_estimate', market: 'US' },
      { valueSource: 'app_estimate', market: 'EU' },
    ]);
    expect(s.label).toBeNull();
    expect(s.us + s.eu + s.unknownCount).toBe(0);
  });

  it('survives junk without throwing', () => {
    expect(summariseMarkets([{}, { valueSource: 'catalog_model' }]).label).toBeNull();
  });
});
