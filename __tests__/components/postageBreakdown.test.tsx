/**
 * Item + postage = total (Vinted's model, 2026-10-16). Walked: "Pay the seller"
 * read "Agreed amount EUR 19" on a EUR 19 + 2,50 trade.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { PostageBreakdown } from '@/components/p2p/PostageBreakdown';
import { formatPrice } from '@/lib/format';

const colors = { text: '#000', muted: '#888', border: '#ddd' };
const fmt = (n: number) => formatPrice(n, 'EUR', 'nl-NL' as never, { exact: true });

it('adds the seller postage on top of the agreed item amount', () => {
  const { getByText } = render(<PostageBreakdown amount={19} shipping={2.5} format={fmt} colors={colors} totalLabel="Total to pay" />);
  expect(getByText('€19')).toBeTruthy();
  expect(getByText('€2,50')).toBeTruthy();
  expect(getByText('€21,50')).toBeTruthy();
  expect(getByText('Total to pay')).toBeTruthy();
});

it('says postage is to be agreed, and shows no total, when the seller stated none', () => {
  const { getByText, queryByText } = render(<PostageBreakdown amount={19} shipping={null} format={fmt} colors={colors} />);
  expect(getByText(/agree it with the seller/)).toBeTruthy();
  expect(queryByText('Total')).toBeNull();
});

it('free postage is free, not missing', () => {
  const { getByText } = render(<PostageBreakdown amount={19} shipping={0} format={fmt} colors={colors} />);
  expect(getByText('Free')).toBeTruthy();
  expect(getByText('Total')).toBeTruthy();
});
