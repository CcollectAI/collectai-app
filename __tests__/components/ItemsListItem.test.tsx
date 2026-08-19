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

describe('ItemsListItem — the row shows NO purchase figures', () => {
  /**
   * "Paid EUR X" and the profit/loss delta were removed 2026-08-19, reported
   * as clutter: a ~56pt row carrying value, source chip, paid AND P/L is four
   * figures per item, and this is a REFERENCE ROW, not a position blotter
   * (docs/ui-playbook.md, "a list card is a reference row, not a call to
   * action" — the same rule that took two buttons off the watchlist card).
   *
   * Seven tests pinned the old behaviour. They are replaced rather than
   * deleted, because the useful half of a test that pins a removed feature is
   * the guard against it coming back
   * (learning_a_red_test_is_often_evidence_the_fix_landed — the DECISION
   * decides, not the test). Both numbers still live on the item's own screen.
   */
  it('never renders a Paid line, whatever the purchase data says', () => {
    for (const purchasePriceEur of [undefined, null, 0, 100]) {
      const { unmount } = render(
        <ItemsListItem item={makeItem({ value: 150, purchasePriceEur })} {...baseProps} />);
      expect(screen.queryByText(/Paid /)).toBeNull();
      unmount();
    }
  });

  it('never renders a P/L delta, in either direction', () => {
    // 150 vs 100 was "+EUR 50 (+50%)"; 60 vs 100 was "−EUR 40 (−40%)".
    for (const value of [150, 60]) {
      const { unmount } = render(
        <ItemsListItem item={makeItem({ value, purchasePriceEur: 100 })} {...baseProps} />);
      expect(screen.queryByText(/\(\+\d+%\)/)).toBeNull();
      expect(screen.queryByText(/\(−\d+%\)/)).toBeNull();
      unmount();
    }
  });

  it('drops the P/L screen-reader label with the line it described', () => {
    render(<ItemsListItem item={makeItem({ value: 150, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.queryByLabelText(/percent versus purchase price/)).toBeNull();
  });

  it('still renders the item value — only the purchase figures went', () => {
    render(<ItemsListItem item={makeItem({ value: 150, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.getByText(/150/)).toBeTruthy();
  });

  it('has no send-to-chat button', () => {
    // The paper-plane button was DEAD: app/(tabs)/items.tsx rendered
    // <ShareToChatSheet> only inside the first-run loading branch, so on every
    // screen where a row was visible the sheet did not exist. Tapping it set
    // state and opened nothing. Removed with its whole chain 2026-08-19.
    render(<ItemsListItem item={makeItem()} {...baseProps} />);
    expect(screen.queryByLabelText(/Send .* to a chat/)).toBeNull();
  });
});

describe('ItemsListItem — unpriced items', () => {
  // The intake pipeline stores estimated_value = 0 when it cannot price an
  // item (an ISBN scan with no market comps), so "€ 0" in the row read as
  // "worthless" when it meant "unknown". ItemDetailsCard has said "Cannot
  // estimate value" for this state since 2026-07; the list row still showed
  // "€ 0", so the same item contradicted itself between the two screens.
  // These pin the row to the shared rule in @/lib/format.

  it('renders the unpriced label instead of a zero price when value is 0', () => {
    render(<ItemsListItem item={makeItem({ value: 0 })} {...baseProps} />);
    expect(screen.getByText('Cannot estimate value')).toBeTruthy();
    // No formatted zero anywhere in the row.
    expect(screen.queryByText(/^\D*0\D*$/)).toBeNull();
  });

  it('announces the unpriced state to screen readers rather than "0"', () => {
    render(<ItemsListItem item={makeItem({ value: 0 })} {...baseProps} />);
    expect(
      screen.getByLabelText('Charizard 1st Edition, Cannot estimate value'),
    ).toBeTruthy();
  });

  it('still renders a real price when the item IS priced', () => {
    render(<ItemsListItem item={makeItem({ value: 100 })} {...baseProps} />);
    expect(screen.queryByText('Cannot estimate value')).toBeNull();
    expect(screen.getByText(/100/)).toBeTruthy();
  });

  it('shows the unpriced label alone — there is no paid line to keep', () => {
    // This asserted the opposite until 2026-08-19 ("unpriced must not suppress
    // data we DO have"). True at the time; the paid line has since been
    // removed from the row entirely, so the unpriced label now stands alone.
    render(<ItemsListItem item={makeItem({ value: 0, purchasePriceEur: 100 })} {...baseProps} />);
    expect(screen.getByText('Cannot estimate value')).toBeTruthy();
    expect(screen.queryByText(/Paid /)).toBeNull();
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

  it('renders no meta line at all when there is no collection', () => {
    render(<ItemsListItem item={makeItem({ collectionName: '' })} {...baseProps} />);
    // Was "pokemon – " with a dangling separator, then "[pill] – Base Set".
    // The category pill left the row on 2026-08-19 (the section heading above
    // every row already names the category, and that heading is now the tap
    // target), so there is no separator left to dangle and nothing to render
    // when the collection is empty.
    expect(screen.queryByText(/–/)).toBeNull();
  });

  it('shows the collection on its own, with no separator in front of it', () => {
    render(<ItemsListItem item={makeItem({ collectionName: 'Base Set' })} {...baseProps} />);
    expect(screen.getByText('Base Set')).toBeTruthy();
    expect(screen.queryByText(/– Base Set/)).toBeNull();
  });

  it('does not render the category on the row — the section heading owns it', () => {
    render(<ItemsListItem item={makeItem({ category: 'mtg' })} {...baseProps} />);
    expect(screen.queryByText('Magic: The Gathering')).toBeNull();
    expect(screen.queryByLabelText(/View .* category/)).toBeNull();
  });

  it('omits the detail line entirely for a sparse item', () => {
    render(<ItemsListItem item={makeItem()} {...baseProps} />);
    expect(screen.queryByText(/·/)).toBeNull();
  });
});
