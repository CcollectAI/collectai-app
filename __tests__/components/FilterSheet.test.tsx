import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn().mockResolvedValue(null),
  setItem: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'light',
    JUDGMENT_LOCKED: 'locked',
    ALERT_TRIGGERED: 'alert',
    CONFIDENCE_HIGH: 'high',
  },
}));
jest.mock('../../src/lib/logger', () => ({
  logger: { warn: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

import { FilterSheet, FilterConfig } from '../../src/components/FilterSheet';

const mockColors = {
  background: '#F7FAF9',
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  accent: '#81D8D0',
  border: '#E2E8F0',
};

const defaultConfig: FilterConfig = {
  sortBy: 'value_desc',
  categories: [],
  conditions: [],
  priceMin: null,
  priceMax: null,
};

function renderFilterSheet(overrides?: Partial<{
  visible: boolean;
  currentConfig: FilterConfig;
  onApply: (c: FilterConfig) => void;
  onClose: () => void;
}>) {
  const props = {
    visible: true,
    currentConfig: defaultConfig,
    availableCategories: ['pokemon', 'lego', 'funko'],
    availableConditions: ['Mint', 'Near Mint', 'Good'],
    colors: mockColors,
    onApply: jest.fn(),
    onClose: jest.fn(),
    ...overrides,
  };
  return { ...render(<FilterSheet {...props} />), ...props };
}

describe('FilterSheet', () => {
  it('renders the title text', () => {
    renderFilterSheet();
    expect(screen.getByText('Filters & Sort')).toBeTruthy();
  });

  it('does not render content when not visible', () => {
    renderFilterSheet({ visible: false });
    expect(screen.queryByText('Value (High → Low)')).toBeNull();
  });

  it('renders sort options', () => {
    renderFilterSheet();
    expect(screen.getByText('Value (High → Low)')).toBeTruthy();
    expect(screen.getByText('Name (A → Z)')).toBeTruthy();
  });

  it('calls onApply when Apply is pressed', async () => {
    const { onApply } = renderFilterSheet();
    const applyBtn = screen.getByText('Apply Filters');
    fireEvent.press(applyBtn);
    await waitFor(() => {
      expect(onApply).toHaveBeenCalled();
    });
  });

  it('renders reset button text', () => {
    renderFilterSheet();
    const resetButtons = screen.getAllByText(/Reset/i);
    expect(resetButtons.length).toBeGreaterThan(0);
  });

  it('tapping a sort option does not crash', () => {
    renderFilterSheet();
    fireEvent.press(screen.getByText('Name (A → Z)'));
    expect(screen.getByText('Name (A → Z)')).toBeTruthy();
  });

  it('renders close button with accessibility label', () => {
    renderFilterSheet();
    expect(screen.getByLabelText('Close filters')).toBeTruthy();
  });
});
