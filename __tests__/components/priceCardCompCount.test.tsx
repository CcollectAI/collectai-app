/**
 * PriceCard — the single-comp branch, RENDERED.
 *
 * tsc proves the types line up; it cannot prove the component mounts. These
 * exist so a labelling change does not need a TestFlight build to find out it
 * crashes, and so the "=== 1" boundary is checked at 0, 1, 2 and undefined
 * rather than assumed.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { PriceCard } from '@/components/PriceCard';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      background: '#fff', card: '#fff', text: '#000', muted: '#888', border: '#ddd',
      accent: '#40C9C6', success: '#059669', danger: '#EF4444', warning: '#F59E0B',
      brand: { base: '#81D8D0', dark: '#5FBFB6', darker: '#44A9A1', light: '#AEE6E1', lighter: '#E6F7F5' },
    },
  }),
}));

const estimate = {
  priceBand: { q10: 100, q50: 200, q90: 300 },
  currency: 'EUR' as const,
  confidenceTier: 'medium' as const,
};

describe('PriceCard comp count', () => {
  it('renders at one comp without crashing, and names it a sale', () => {
    const { getByText, queryByText } = render(
      <PriceCard estimate={estimate as never} compCount={1} />,
    );
    expect(getByText('Last recorded sale')).toBeTruthy();
    expect(queryByText('Estimated Value')).toBeNull();
    // The degenerate range must not render as a precise interval.
    expect(getByText(/not enough for a range/i)).toBeTruthy();
  });

  it.each([0, 2, 5])('calls it an estimate at %i comps', (n) => {
    const { getByText, queryByText } = render(
      <PriceCard estimate={estimate as never} compCount={n} />,
    );
    expect(getByText('Estimated Value')).toBeTruthy();
    expect(queryByText('Last recorded sale')).toBeNull();
  });

  it('falls back to an estimate when the count is unknown', () => {
    // undefined must behave like "many", not like 1 — a truthiness check would
    // have made undefined and 0 identical.
    const { getByText } = render(<PriceCard estimate={estimate as never} />);
    expect(getByText('Estimated Value')).toBeTruthy();
  });

  it('shows the real range whenever there is more than one comp', () => {
    const { getByText } = render(
      <PriceCard estimate={estimate as never} compCount={4} />,
    );
    expect(getByText(/Range:/)).toBeTruthy();
  });
});
