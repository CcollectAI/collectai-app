/**
 * Walked as buyer 2026-10-15: the seller had added no payment handles, every
 * rail opened the provider's front page, and nothing on "Pay the seller" said
 * where the money goes.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react-native';

const mockRails = jest.fn();
jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: {
    p2pListPaymentRails: (...a: unknown[]) => mockRails(...a),
    p2pListCarriers: jest.fn().mockResolvedValue([]),
    p2pGetDeliveryAddress: jest.fn().mockResolvedValue(null),
    p2pSetDeliveryAddress: jest.fn(),
  },
}));
jest.mock('@/components/BottomSheetModal', () => ({
  BottomSheetModal: ({ children }: { children: React.ReactNode }) => children,
}));
jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('@/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: {} }));
jest.mock('@/components/Toast', () => ({ ToastHost: () => null, useToast: () => ({ showToast: jest.fn() }) }));
jest.mock('@/lib/settings', () => ({ useSettings: () => ({ settings: { currency: 'EUR', numberLocale: 'nl-NL' } }) }));
jest.mock('@/motion', () => {
  const { Pressable } = require('react-native');
  return { AnimatedPressable: Pressable };
});

import { SettleUpSheet } from '@/components/p2p/SettleUpSheet';

const colors = { text: '#000', muted: '#888', card: '#fff', border: '#ddd', accent: '#0aa', accentText: '#fff', background: '#fff' };
const HINT = /hasn't added payment details/;
const rail = (pay_url: string | null) => ({ key: 'paypal', label: 'PayPal', url: 'https://paypal.com', pay_url, coverage: 'x', reversible: null });

it('tells the buyer when no rail carries the seller handle', async () => {
  mockRails.mockResolvedValue({ rails: [rail(null)], disclaimer: '' });
  const { findByText } = render(<SettleUpSheet visible mode="pay" offerId="o1" isBuyer onClose={jest.fn()} amountLabel="€19" colors={colors} />);
  expect(await findByText(HINT)).toBeTruthy();
});

it('says nothing when the seller gave a handle', async () => {
  mockRails.mockResolvedValue({ rails: [rail('https://paypal.me/seller')], disclaimer: '' });
  const { queryByText, findByText } = render(<SettleUpSheet visible mode="pay" offerId="o1" isBuyer onClose={jest.fn()} amountLabel="€19" colors={colors} />);
  await findByText('PayPal');
  await waitFor(() => expect(queryByText(HINT)).toBeNull());
});
