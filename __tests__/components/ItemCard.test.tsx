/**
 * ItemCard component tests.
 *
 * Verifies that ItemCard renders the item title, category label,
 * and conditionally displays the value badge.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';
import type { ItemRow } from '../../src/hooks/useItems';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock the theme module to avoid the theme.ts <-> theme/ directory conflict
jest.mock('../../src/theme', () => ({
  theme: {
    colors: {
      card: '#FFFFFF',
      text: '#0F172A',
      muted: '#64748B',
      success: '#10B981',
    },
    radius: { xl: 24 },
    shadow: {
      card: {
        shadowColor: '#000',
        shadowOpacity: 0.06,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 4 },
        elevation: 2,
      },
    },
  },
}));

// expo-image: replace with a plain <View> so we don't need native binaries
jest.mock('expo-image', () => {
  const { View } = require('react-native');
  return {
    Image: (props: any) => <View testID="expo-image" {...props} />,
  };
});

// Mock the useItems module so the type import works (and avoid supabase dep)
jest.mock('../../src/hooks/useItems', () => ({}));

// Mock the asset require() for the placeholder image
jest.mock('../../assets/images/placeholder.png', () => 1);

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: true, currency: 'USD', numberLocale: 'en-US' }, updateSettings: jest.fn(), ready: true }),
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

// Now import ItemCard after mocks are set up
import ItemCard from '../../src/components/ItemCard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<ItemRow> = {}): ItemRow {
  return {
    id: 'item-1',
    title: 'Charizard Base Set',
    category: 'Pokemon',
    image_url: 'https://example.com/charizard.jpg',
    value: 350,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ItemCard', () => {
  it('renders the item title', () => {
    render(<ItemCard item={makeItem()} />);
    expect(screen.getByText('Charizard Base Set')).toBeTruthy();
  });

  it('renders the curated name for a SLUG, which is what items.category holds', () => {
    // Was `category: 'Yu-Gi-Oh'` expecting itself back. That value is in
    // neither vocabulary — the slug is `yugioh` and the curated name is
    // `Yu-Gi-Oh!` with the bang — so `categoryDisplayName` correctly fell
    // through to title-casing and produced "Yu Gi Oh". The test asserted a
    // fixture the app never stores (all 148 prod rows are slugs).
    render(<ItemCard item={makeItem({ category: 'yugioh' })} />);
    expect(screen.getByText('Yu-Gi-Oh!')).toBeTruthy();
  });

  it('leaves an already-resolved display name alone', () => {
    // The other half of `categoryDisplayName`: it is handed values from both
    // vocabularies, and re-formatting a resolved name mangles it.
    render(<ItemCard item={makeItem({ category: 'Yu-Gi-Oh!' })} />);
    expect(screen.getByText('Yu-Gi-Oh!')).toBeTruthy();
  });

  it('shows "Uncategorized" when category is undefined', () => {
    render(<ItemCard item={makeItem({ category: undefined })} />);
    expect(screen.getByText('Uncategorized')).toBeTruthy();
  });

  it('displays the value badge when value is a number', () => {
    render(<ItemCard item={makeItem({ value: 42 })} />);
    expect(screen.getByText('$42')).toBeTruthy();
  });

  it('hides the value badge when value is undefined', () => {
    render(<ItemCard item={makeItem({ value: undefined })} />);
    expect(screen.queryByText(/^\$/)).toBeNull();
  });
});
