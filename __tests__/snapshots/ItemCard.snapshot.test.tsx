/**
 * Snapshot tests for ItemCard component.
 * Catches unintended visual regressions in the item card layout.
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import type { ItemRow } from '../../src/hooks/useItems';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock('../../src/theme', () => ({
  theme: {
    colors: {
      card: '#FFFFFF',
      text: '#0F172A',
      muted: '#64748B',
      success: '#10B981',
      brand: { base: '#81D8D0' },
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

jest.mock('expo-image', () => {
  const { View } = require('react-native');
  return {
    Image: (props: any) => <View testID="expo-image" {...props} />,
  };
});

jest.mock('../../src/hooks/useItems', () => ({}));
jest.mock('../../assets/images/placeholder.png', () => 1);
jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: true, currency: 'EUR' }, updateSettings: jest.fn(), ready: true }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(), notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

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
// Snapshot Tests
// ---------------------------------------------------------------------------

describe('ItemCard snapshots', () => {
  it('matches snapshot with image and value', () => {
    const tree = render(<ItemCard item={makeItem()} />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot without image (placeholder)', () => {
    const tree = render(
      <ItemCard item={makeItem({ image_url: undefined })} />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot without value', () => {
    const tree = render(
      <ItemCard item={makeItem({ value: undefined })} />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with condition badge (grading-eligible category)', () => {
    const tree = render(
      <ItemCard
        item={makeItem({
          category: 'pokemon',
          condition: 'PSA 10',
        })}
      />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with no category', () => {
    const tree = render(
      <ItemCard item={makeItem({ category: undefined })} />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
