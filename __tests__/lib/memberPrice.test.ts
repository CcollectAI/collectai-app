/**
 * A member's own number is shown to the cent; an estimate and an FX-converted
 * figure are not. Walked 2026-10-15: "€23 total incl. shipping" for €20 + €2,50
 * and "Send offer · €18" on a €17,50 offer.
 */
import { formatMemberPrice } from '@/lib/memberPrice';
import { formatPrice } from '@/lib/format';

const nl = { currency: 'EUR' as const, fxRates: { USD: 1.1 } as never, numberLocale: 'nl-NL' as never };

it('shows cents a member typed, and none when there are none', () => {
  expect(formatMemberPrice(22.5, 'EUR', nl)).toBe('€22,50');
  expect(formatMemberPrice(17.5, 'EUR', nl)).toBe('€17,50');
  expect(formatMemberPrice(20, 'EUR', nl)).toBe('€20');
});

it('drops to whole units after FX conversion — the cents are an estimate then', () => {
  expect(formatMemberPrice(22.5, 'USD', nl)).toBe('€20');
});

it('leaves estimates at whole units (the default is unchanged)', () => {
  expect(formatPrice(22.5, 'EUR', 'nl-NL' as never)).toBe('€23');
  expect(formatPrice(22.5, 'EUR', 'nl-NL' as never, { exact: true })).toBe('€22,50');
});

it('renders a missing amount as a dash', () => {
  expect(formatMemberPrice(null, 'EUR', nl)).toBe('—');
});
