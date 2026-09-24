/**
 * Deal checks read as sentences, and a guessed shipping cost reads as a guess.
 * 2026-09-24: the screen printed engine strings and showed our €22.50 estimate
 * as the listing's own shipping.
 */
import { policyCheckLine, shippingLine } from '@/lib/dealChecks';

const t = (_k: string, o?: Record<string, unknown>) =>
  String(o?.defaultValue ?? '').replace(/\{\{(\w+)\}\}/g, (_m, k) => String(o?.[k] ?? ''));

describe('dealChecks', () => {
  it('turns a code into a sentence, never an engine string', () => {
    expect(policyCheckLine({ code: 'price', ok: true, max: 30 }, t)).toMatch(/^Within your .*30.* limit$/);
    expect(policyCheckLine({ code: 'source', ok: true }, t)).toBe('From a marketplace you chose');
    expect(policyCheckLine({ code: 'card', ok: false, number: '161' }, t)).toBe('A different card, not #161');
  });

  it('states an estimated shipping as a range to check', () => {
    const line = shippingLine({ code: 'price', ok: true, shippingEstimated: true, shippingMin: 5, shippingMax: 40 }, t);
    expect(line).toMatch(/^Shipping not stated — usually .*5.*–.*40.* to you\. Check the listing\.$/);
  });

  it('shows stated shipping as an amount, and nothing when free', () => {
    expect(shippingLine({ code: 'price', ok: true, shipping: 2 }, t)).toMatch(/^Plus .*2.* shipping$/);
    expect(shippingLine({ code: 'price', ok: true, shipping: 0 }, t)).toBeNull();
  });

  it('ignores a code it does not know', () => {
    expect(policyCheckLine({ code: 'future_check', ok: true }, t)).toBeNull();
  });
});
