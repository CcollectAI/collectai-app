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

/**
 * Category control — bubble menu, not chips (2026-08-29).
 *
 * Requested as "i dont want chips menus but rather bubble ios menus". The risk
 * in that change is silent: the category filter is MULTI-select
 * (`config.categories` is an array and the marketplace really does filter on
 * several at once), and the obvious implementation — swapping in the existing
 * single-select CompactSelect — would look exactly right and quietly remove
 * that. These pin the behaviour, not the styling.
 */
describe('FilterSheet — category bubble menu', () => {
  const openCategorySection = () => {
    fireEvent.press(screen.getByLabelText(/^Category filter/));
  };

  it('shows a single trigger, not one control per category', () => {
    renderFilterSheet();
    openCategorySection();
    // The trigger states the selection. Three categories are available, so a
    // chip grid would render three separate controls here.
    expect(screen.getByLabelText('Category, all categories')).toBeTruthy();
    expect(screen.queryByLabelText('pokemon')).toBeNull();
    expect(screen.queryByLabelText('lego')).toBeNull();
  });

  it('opens a menu listing every category', () => {
    renderFilterSheet();
    openCategorySection();
    fireEvent.press(screen.getByLabelText('Category, all categories'));
    expect(screen.getByLabelText('pokemon')).toBeTruthy();
    expect(screen.getByLabelText('lego')).toBeTruthy();
    expect(screen.getByLabelText('funko')).toBeTruthy();
    expect(screen.getByLabelText(/^All categories/)).toBeTruthy();
  });

  it('KEEPS multi-select — two categories can be chosen at once', async () => {
    const onApply = jest.fn();
    renderFilterSheet({ onApply });
    openCategorySection();
    fireEvent.press(screen.getByLabelText('Category, all categories'));
    fireEvent.press(screen.getByLabelText('pokemon'));
    fireEvent.press(screen.getByLabelText(/^lego/));
    fireEvent.press(screen.getByLabelText('Done choosing categories'));
    fireEvent.press(screen.getByText('Apply Filters'));
    await waitFor(() => expect(onApply).toHaveBeenCalled());
    const applied = onApply.mock.calls[0][0] as FilterConfig;
    expect(applied.categories.sort()).toEqual(['lego', 'pokemon']);
  });

  it('"All categories" CLEARS rather than inventing a sentinel value', async () => {
    const onApply = jest.fn();
    renderFilterSheet({
      currentConfig: { ...defaultConfig, categories: ['pokemon'] },
      onApply,
    });
    openCategorySection();
    fireEvent.press(screen.getByLabelText('Category, 1 selected'));
    fireEvent.press(screen.getByLabelText(/^All categories/));
    fireEvent.press(screen.getByLabelText('Done choosing categories'));
    fireEvent.press(screen.getByText('Apply Filters'));
    await waitFor(() => expect(onApply).toHaveBeenCalled());
    // An empty array already means "unfiltered" to every downstream reader.
    // A sentinel like 'all' would be a value no category ever equals.
    expect((onApply.mock.calls[0][0] as FilterConfig).categories).toEqual([]);
  });

  it('the trigger says what is selected without opening it', () => {
    renderFilterSheet({
      currentConfig: { ...defaultConfig, categories: ['pokemon', 'lego'] },
    });
    openCategorySection();
    expect(screen.getByLabelText('Category, 2 selected')).toBeTruthy();
  });
});
