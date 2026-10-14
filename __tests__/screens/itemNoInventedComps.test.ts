import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * The price explanation must not invent its sources (2026-10-14).
 *
 * With no evidence, app/item/[id].tsx used to fill "Comparable sources" with
 * `{ source: 'eBay', count: 12, avgPrice: q50 * 0.95, dateRange: 'Last 90 days' }`
 * and a TCGPlayer row at 1.02x — numbers derived from the estimate they claimed
 * to support. A source row must come from evidence or not exist.
 */
describe('item screen — comp sources come from evidence only', () => {
  const src = readFileSync(join(__dirname, '../../app/item/[id].tsx'), 'utf8');
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

  it('derives no avgPrice from the estimate itself', () => {
    expect(code).not.toMatch(/avgPrice:\s*priceEstimate/);
  });

  it('hard-codes no comp count', () => {
    expect(code).not.toMatch(/count:\s*\d+\s*,\s*avgPrice/);
  });
});
