/**
 * When the app may ask "use our market price, or keep yours?".
 *
 * Manual add already replaced the member's number silently — it saves what you
 * typed, then `revalueItem` writes a catalogue valuation into the TOP of the
 * value chain. The prompt is the same mechanism with the member told. These
 * tests pin when the question is worth asking, because a prompt that appears
 * when there is nothing to decide is noise, and one that reappears after an
 * answer reads as the app ignoring you.
 */
import { shouldOfferComp } from '@/components/item/MarketCompPrompt';

const base = {
  valueSource: 'catalog_model',
  currentValue: 62,
  userEstimate: 50,
  existingChoice: null as string | null,
};

describe('shouldOfferComp', () => {
  it('asks when a market comp disagrees with what the member typed', () => {
    expect(shouldOfferComp(base)).toBe(true);
  });

  it('accepts any comp-backed source', () => {
    for (const s of ['catalog_daily', 'catalog_model', 'quick_scan']) {
      expect(shouldOfferComp({ ...base, valueSource: s })).toBe(true);
    }
  });

  it('never asks when the shown value is itself an estimate', () => {
    // There is no comp to offer — the question would be "use your number or
    // your number?".
    for (const s of ['user_estimate', 'app_estimate', 'none', undefined, null]) {
      expect(shouldOfferComp({ ...base, valueSource: s })).toBe(false);
    }
  });

  it('never asks when the member typed nothing to keep', () => {
    for (const v of [undefined, null, 0]) {
      expect(shouldOfferComp({ ...base, userEstimate: v as number })).toBe(false);
    }
  });

  it('never asks twice — either answer closes it', () => {
    expect(shouldOfferComp({ ...base, existingChoice: 'mine' })).toBe(false);
    expect(shouldOfferComp({ ...base, existingChoice: 'market' })).toBe(false);
  });

  it('does not ask when the two numbers agree', () => {
    expect(shouldOfferComp({ ...base, currentValue: 50, userEstimate: 50 })).toBe(false);
    // A cent of float noise is not a disagreement.
    expect(shouldOfferComp({ ...base, currentValue: 50.004, userEstimate: 50 })).toBe(false);
    expect(shouldOfferComp({ ...base, currentValue: 50.01, userEstimate: 50 })).toBe(true);
  });

  it('does not ask when there is no market number to offer', () => {
    for (const v of [undefined, null, 0]) {
      expect(shouldOfferComp({ ...base, currentValue: v as number })).toBe(false);
    }
  });
});
