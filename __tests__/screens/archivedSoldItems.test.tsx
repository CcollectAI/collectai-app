/**
 * A card that left by a SALE must not offer Restore (walked 2026-10-16): the
 * screen tested `source === 'marketplace'` (the BUYER's row), so a sold card
 * read "You archived this" with a working Restore.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react-native';

jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: { listP2PListings: jest.fn().mockResolvedValue({ listings: [
    { item_id: 'sold-1', status: 'sold' },
    { item_id: 'live-1', status: 'active' },
  ] }) },
}));
jest.mock('@/data', () => ({
  dataProvider: {
    listArchivedItems: jest.fn().mockResolvedValue([
      { id: 'sold-1', name: 'DEMO Pikachu', category: 'pokemon' },
      { id: 'mine-1', name: 'Luffy Vol 105', category: 'manga' },
    ]),
    unarchiveItem: jest.fn(),
  },
}));
jest.mock('@shopify/flash-list', () => {
  const { FlatList } = require('react-native');
  return { FlashList: FlatList };
});
jest.mock('expo-router', () => ({ Stack: { Screen: () => null } }));
jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('@/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: {} }));
jest.mock('@/motion', () => {
  const { Pressable } = require('react-native');
  return { AnimatedPressable: Pressable };
});
jest.mock('@/components/Toast', () => ({ useToast: () => ({ showToast: jest.fn() }), ToastHost: () => null }));
jest.mock('@/components/QuickNavBar', () => ({ QuickNavBar: () => null }));
jest.mock('@/components/ScreenErrorBoundary', () => ({ ScreenErrorBoundary: ({ children }: { children: React.ReactNode }) => children }));
jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { card: '#fff', border: '#ddd', text: '#000', muted: '#888', accent: '#0aa', background: '#fff' } }),
}));

import ArchivedScreen from '../../app/archived';

it('a sold card says Sold and has no Restore; your own archived card keeps it', async () => {
  const { findByText, queryByLabelText, getByLabelText } = render(<ArchivedScreen />);
  await findByText('Luffy Vol 105');
  await waitFor(() => expect(queryByLabelText('Restore DEMO Pikachu to your collection')).toBeNull());
  expect(getByLabelText('Restore Luffy Vol 105 to your collection')).toBeTruthy();
  expect(await findByText(/Sold on Sparrow/)).toBeTruthy();
});
