/**
 * ItemsListItem — paid-price + P/L surface tests.
 *
 * The "paid for" data was captured in items.purchase_price_eur for months
 * but never read back into the items list. This test pins the new behavior
 * so a future refactor can't silently drop the surface again.
 *
 * Covers: hidden when no purchase data; rendered when present; positive
 * delta in green, negative in red; suppressed when predicted value is 0.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

// Theme — we read colors.success / colors.danger directly in the SUT, so
// mock concrete values we can assert against.
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      card: '#FFFFFF',
      text: '#0F172A',
      muted: '#64748B',
      border: '#E2E8F0',
      accent: '#81D8D0',
      success: '#10B981',
      danger: '#EF4444',
      background: '#FFFFFF',
    },
  }),
}));

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: { hapticsEnabled: true, currency: 'EUR', numberLocale: 'de-DE', animationsEnabled: false },
    updateSettings: jest.fn(),
    ready: true,
  }),
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

// CategoryPill — render a plain text node so we don't pull category data.
jest.mock('../../src/components/CategoryPill', () => {
  const { Text } = require('react-native');
  return { CategoryPill: ({ label }: { label: string }) => <Text>{label}</Text> };
});

// SwipeableRow — render children straight through, no gesture handler.
jest.mock('../../src/components/SwipeableRow', () => {
  const { View } = require('react-native');
  return {
    SwipeableRow: ({ children }: { children: React.ReactNode }) => <View>{children}</View>,
    SwipeActions: { delete: (cb: () => void) => ({ key: 'delete', label: 'Delete', icon: 'trash', color: 'red', onPress: cb }) },
  };
});

// AnimatedPressable — plain Pressable, no animated wrapper.
jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return { AnimatedPressable: Pressable };
});

import { ItemsListItem } from '../../src/components/items/ItemsListItem';

type MakeItemOverrides = {
  value?: number;
  purchasePriceEur?: number | null;
  purchasedAt?: string | null;
  collectionName?: string;
  condition?: string;
  brand?: string;
  year?: number;
  series?: string;
  editionLabel?: string;
};

function makeItem(overrides: MakeItemOverrides = {}) {
  return {
    id: 'i1',
    name: 'Charizard 1st Edition',
    category: 'pokemon',
    collectionName: 'Base Set',
    value: 100,
    ...overrides,
  };
}

const baseProps = {
  isMultiSelectMode: false,
  isSelected: false,
  onPress: jest.fn(),
  onLongPress: jest.fn(),
};

describe('ItemsListItem — paid-price + P/L surface', () => {
  it('hides the paid line when no purchase data is present', () => {
    render(<ItemsListItem item={makeItem()} {...baseProps} />);
    expect(screen.queryByText(/Paid /)).toBeNull();
    // Predicted value still renders.
    expect(screen.getByText(/100/)).toBeTruthy();
  });

  it('hides the paid line when purchasePriceEur is explicitly null (item has no record)', () => {
    render(<ItemsListItem item={makeItem({ purchasePriceEur: null })} {...baseProps} />);
    expect(screen.queryByText(/Paid /)).toBeNull();
  });

  it('hides the paid line when purchasePriceEur is 0 (treated as not set)', () => {
    // 0 is not a meaningful "amount paid" — surface treats it as no data
    // rather than rendering "Paid €0" + a misleading +infinity% delta.
    render(<ItemsListItem item={makeItem({ purchasePriceEur: 0 })} {...baseProps} />);
    expect(screen.queryByText(/Paid /)).toBeNull();
  });

  it('renders the paid line and a positive P/L delta when value > purchase price', () => {
    render(<ItemsListItem item={makeItem({ value: 150, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.getByText(/Paid /)).toBeTruthy();
    // Positive delta uses + sign and integer percent.
    expect(screen.getByText(/\+.*\(\+50%\)/)).toBeTruthy();
  });

  it('renders a negative P/L delta when value < purchase price', () => {
    render(<ItemsListItem item={makeItem({ value: 60, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.getByText(/Paid /)).toBeTruthy();
    // Negative delta uses Unicode minus and integer percent.
    expect(screen.getByText(/−.*\(−40%\)/)).toBeTruthy();
  });

  it('hides the P/L delta when predicted value is 0 (no model — comparison meaningless)', () => {
    render(<ItemsListItem item={makeItem({ value: 0, purchasePriceEur: 100 })} {...baseProps} />);
    // Paid line is still useful even without a prediction.
    expect(screen.getByText(/Paid /)).toBeTruthy();
    // No P/L delta renders.
    expect(screen.queryByText(/[+−]/)).toBeNull();
  });

  it('exposes a P/L accessibility label so screen readers announce direction + magnitude', () => {
    render(<ItemsListItem item={makeItem({ value: 150, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.getByLabelText(/Up 50 percent versus purchase price/)).toBeTruthy();
  });
});

describe('ItemsListItem — enrichment surface', () => {
  it('renders the brand · year · edition detail line when present', () => {
    render(
      <ItemsListItem
        item={makeItem({ brand: 'WotC', year: 1999, editionLabel: '1st Edition' })}
        {...baseProps}
      />,
    );
    expect(screen.getByText(/WotC · 1999 · 1st Edition/)).toBeTruthy();
  });

  it('renders the condition badge when a condition is set', () => {
    render(
      <ItemsListItem item={makeItem({ condition: 'PSA 9' })} {...baseProps} />,
    );
    expect(screen.getByText('PSA 9')).toBeTruthy();
  });

  it('shows a clean meta line (no dangling dash) when there is no collection', () => {
    render(<ItemsListItem item={makeItem({ collectionName: '' })} {...baseProps} />);
    // The bug rendered "pokemon – " with a trailing separator on every row.
    expect(screen.queryByText(/–\s*$/)).toBeNull();
  });

  it('shows the collection with a separator when present', () => {
    render(<ItemsListItem item={makeItem({ collectionName: 'Base Set' })} {...baseProps} />);
    expect(screen.getByText(/– Base Set/)).toBeTruthy();
  });

  it('omits the detail line entirely for a sparse item', () => {
    render(<ItemsListItem item={makeItem()} {...baseProps} />);
    expect(screen.queryByText(/·/)).toBeNull();
  });
});
