/**
 * The catalogue's Pro price block (2026-09-26). Free members see the teaser;
 * Pro members see the 90-day range; no sales is said, not drawn as zero.
 */
import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { CatalogPriceRangeBlock } from '../../src/components/catalog/CatalogPriceRangeBlock';

const range = { p10: 700, p90: 1500, comps_count: 108, series: [] };
const base = { currency: 'EUR' as const, fxRate: 1, onUnlock: jest.fn(), range: null };

it('locked: the teaser, and it opens the paywall', () => {
  const onUnlock = jest.fn();
  const { getByText, getByRole } = render(<CatalogPriceRangeBlock {...base} state="locked" onUnlock={onUnlock} />);
  expect(getByText(/Sparrow Pro/)).toBeTruthy();
  fireEvent.press(getByRole('button'));
  expect(onUnlock).toHaveBeenCalled();
});

it('ok: the range from p10 to p90', () => {
  const { getByText, queryByText } = render(<CatalogPriceRangeBlock {...base} state="ok" range={range} />);
  expect(getByText(/700.*1[.,]?500/)).toBeTruthy();
  expect(queryByText(/Sparrow Pro/)).toBeNull();
});

it('no sales in the window is said, not shown as a range', () => {
  const { getByText } = render(
    <CatalogPriceRangeBlock {...base} state="ok" range={{ p10: null, p90: null, comps_count: 0, series: [] }} />,
  );
  expect(getByText(/No sales in the last 90 days/)).toBeTruthy();
});
