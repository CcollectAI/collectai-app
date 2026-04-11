import React from 'react';
import { render, screen } from '@testing-library/react-native';

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
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 8,
        elevation: 3,
      },
    },
  },
}));
jest.mock('expo-image', () => ({
  Image: (props: any) => {
    const { View } = require('react-native');
    return <View testID="image" {...props} />;
  },
}));

// Mock the placeholder image require
jest.mock('../../assets/images/placeholder.png', () => 1);
jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: true, currency: 'USD', numberLocale: 'en-US' }, updateSettings: jest.fn(), ready: true }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(), notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

import ItemCard from '../../src/components/ItemCard';

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'test-1',
    title: 'Test Pokemon Card',
    category: 'pokemon',
    value: 25,
    image_url: 'https://example.com/card.jpg',
    ...overrides,
  };
}

describe('ItemCard a11y', () => {
  it('renders item title as accessible text', () => {
    render(<ItemCard item={makeItem()} />);
    expect(screen.getByText('Test Pokemon Card')).toBeTruthy();
  });

  it('renders category text', () => {
    render(<ItemCard item={makeItem({ category: 'lego' })} />);
    expect(screen.getByText('lego')).toBeTruthy();
  });

  it('shows value when present', () => {
    render(<ItemCard item={makeItem({ value: 50 })} />);
    expect(screen.getByText('$50')).toBeTruthy();
  });
});
