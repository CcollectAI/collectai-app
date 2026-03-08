import React from 'react';
import { render, screen } from '@testing-library/react-native';

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

const config: FilterConfig = {
  sortBy: 'value_desc',
  categories: [],
  conditions: [],
  priceMin: null,
  priceMax: null,
};

describe('FilterSheet a11y', () => {
  it('close button has accessibility label', () => {
    render(
      <FilterSheet
        visible={true}
        currentConfig={config}
        availableCategories={[]}
        availableConditions={[]}
        colors={mockColors}
        onApply={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText('Close filters')).toBeTruthy();
  });

  it('Apply button text is visible', () => {
    render(
      <FilterSheet
        visible={true}
        currentConfig={config}
        availableCategories={[]}
        availableConditions={[]}
        colors={mockColors}
        onApply={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText('Apply Filters')).toBeTruthy();
  });

  it('sort options have readable labels', () => {
    render(
      <FilterSheet
        visible={true}
        currentConfig={config}
        availableCategories={[]}
        availableConditions={[]}
        colors={mockColors}
        onApply={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText('Value (High → Low)')).toBeTruthy();
    expect(screen.getByText('Name (A → Z)')).toBeTruthy();
  });
});
