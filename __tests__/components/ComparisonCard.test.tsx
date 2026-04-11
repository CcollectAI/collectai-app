import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { ComparisonCard } from '@/components/ComparisonCard';
import type { QuickScanResult } from '@/data/types';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      background: '#fff', card: '#fff', text: '#000', muted: '#888', border: '#ddd',
      accent: '#40C9C6', success: '#059669', danger: '#EF4444',
      brand: { base: '#81D8D0', dark: '#5FBFB6', darker: '#44A9A1', light: '#AEE6E1', lighter: '#E6F7F5' },
    },
  }),
}));

jest.mock('@/lib/format', () => ({
  formatPrice: (val: number, cur: string) => `${cur} ${val.toFixed(2)}`,
}));

jest.mock('@/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: true }, updateSettings: jest.fn(), ready: true }),
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

const makeResult = (name: string, price: number): QuickScanResult => ({
  attributes: { category: 'pokemon', conditionGuess: 'near_mint', editionGuess: '1st Edition' },
  prediction: {
    name,
    estimatedLow: price * 0.8,
    estimatedMid: price,
    estimatedHigh: price * 1.2,
    currency: 'EUR',
    confidence: 0.85,
  },
});

describe('ComparisonCard', () => {
  const defaultProps = {
    itemA: makeResult('Charizard Base Set', 500),
    itemB: makeResult('Blastoise Base Set', 200),
    imageUriA: 'file://a.jpg',
    imageUriB: 'file://b.jpg',
    currency: 'EUR' as const,
    onKeepA: jest.fn(),
    onKeepB: jest.fn(),
    onKeepBoth: jest.fn(),
    onRetake: jest.fn(),
  };

  it('renders item names', () => {
    const { getByText } = render(<ComparisonCard {...defaultProps} />);
    expect(getByText('Charizard Base Set')).toBeTruthy();
    expect(getByText('Blastoise Base Set')).toBeTruthy();
  });

  it('renders price delta', () => {
    const { getByText } = render(<ComparisonCard {...defaultProps} />);
    expect(getByText(/EUR 300.00/)).toBeTruthy();
  });

  it('calls onKeepA when pressed', () => {
    const { getByText } = render(<ComparisonCard {...defaultProps} />);
    fireEvent.press(getByText('Keep A'));
    expect(defaultProps.onKeepA).toHaveBeenCalled();
  });

  it('calls onKeepB when pressed', () => {
    const { getByText } = render(<ComparisonCard {...defaultProps} />);
    fireEvent.press(getByText('Keep B'));
    expect(defaultProps.onKeepB).toHaveBeenCalled();
  });

  it('calls onKeepBoth when pressed', () => {
    const { getByText } = render(<ComparisonCard {...defaultProps} />);
    fireEvent.press(getByText('Keep Both'));
    expect(defaultProps.onKeepBoth).toHaveBeenCalled();
  });

  it('renders condition comparison', () => {
    const { getAllByText } = render(<ComparisonCard {...defaultProps} />);
    expect(getAllByText('near_mint').length).toBeGreaterThan(0);
  });
});
