/**
 * Snapshot tests for Item extracted components:
 * ItemPriceSection, ItemNotesEditor.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockColors = {
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  accent: '#81D8D0',
  accentText: '#FFFFFF',
  background: '#F8FAFC',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  error: '#EF4444',
  info: '#3B82F6',
  brand: { base: '#81D8D0', dark: '#5FBFB6' },
};

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: mockColors, isDark: false }),
}));

jest.mock('../../src/theme/tokens', () => ({
  radius: { xs: 6, sm: 10, md: 16, lg: 20, xl: 24 },
  spacing: { xxs: 4, xs: 6, sm: 10, md: 14, lg: 18, xl: 24 },
  text: { xs: 10, sm: 12, md: 14, lg: 16, xl: 20, '2xl': 24 },
  fontWeight: {
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800',
  },
  shadow: {
    card: {
      shadowColor: '#000',
      shadowOpacity: 0.06,
      shadowRadius: 8,
      shadowOffset: { width: 0, height: 4 },
      elevation: 2,
    },
  },
  gap: { xxs: 2, xs: 4, sm: 6, md: 8, lg: 10, xl: 12 },
}));

jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => <Pressable {...props} />,
  };
});

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
    ALERT_TRIGGERED: 'ALERT_TRIGGERED',
  },
}));

jest.mock('../../src/config/featureFlags', () => ({
  featureFlags: {
    FEATURE_EXPLAINABLE_AI_INTERFACES: false,
  },
}));

jest.mock('../../src/lib/format', () => ({
  formatPrice: (price: number | undefined, currency?: string) => {
    if (price == null) return '--';
    return currency ? `${currency} ${price}` : `${price}`;
  },
}));

jest.mock('../../src/components/PriceCard', () => ({
  PriceCard: () => null,
}));

jest.mock('../../src/components/PriceConfidenceGauge', () => ({
  PriceConfidenceGauge: ({ confidence }: any) => {
    const { Text } = require('react-native');
    return <Text>Confidence: {confidence}</Text>;
  },
}));

// Import components after mocks
import { ItemPriceSection } from '../../src/components/item/ItemPriceSection';
import { ItemNotesEditor } from '../../src/components/item/ItemNotesEditor';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const toNum = (v: string | number | undefined | null): number | undefined => {
  if (v == null) return undefined;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return isNaN(n) ? undefined : n;
};

// ---------------------------------------------------------------------------
// ItemPriceSection
// ---------------------------------------------------------------------------

describe('ItemPriceSection', () => {
  it('renders with legacy price bands and matches snapshot', () => {
    const tree = render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        q10="100"
        q50="200"
        q90="350"
        confidence="0.85"
        explanation="Based on recent eBay sales"
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={null}
        marketComps={[]}
        toNum={toNum}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders price range text', () => {
    render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        q10="50"
        q50="100"
        q90="150"
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={null}
        marketComps={[]}
        toNum={toNum}
      />,
    );
    expect(screen.getByText('Price range')).toBeTruthy();
  });

  it('renders confidence gauge when confidence provided', () => {
    render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        q10="10"
        q50="20"
        q90="30"
        confidence="0.75"
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={null}
        marketComps={[]}
        toNum={toNum}
      />,
    );
    expect(screen.getByText('Confidence: 0.75')).toBeTruthy();
  });

  it('renders scarcity badge', () => {
    render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={{
          scarcity_score: 8,
          listing_count: 3,
          supply_trend: 'declining',
        }}
        marketComps={[]}
        toNum={toNum}
      />,
    );
    expect(screen.getByText('Rare')).toBeTruthy();
    expect(screen.getByText(/3 listings/)).toBeTruthy();
  });

  it('renders moderate scarcity label', () => {
    render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={{
          scarcity_score: 5,
          listing_count: 12,
          supply_trend: 'stable',
        }}
        marketComps={[]}
        toNum={toNum}
      />,
    );
    expect(screen.getByText('Moderate')).toBeTruthy();
  });

  it('renders market comps', () => {
    render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        explanationExpanded={false}
        onToggleExplanation={jest.fn()}
        scarcityData={null}
        marketComps={[
          { title: 'eBay Sold Listing', source: 'eBay', price: 195, currency: 'EUR' },
          { title: 'TCGPlayer Sale', source: 'TCGPlayer', price: 210, currency: 'USD' },
        ]}
        toNum={toNum}
      />,
    );
    expect(screen.getByText('eBay Sold Listing')).toBeTruthy();
    expect(screen.getByText('TCGPlayer Sale')).toBeTruthy();
    expect(screen.getByText(/Comparable Sales/)).toBeTruthy();
  });

  it('matches snapshot with scarcity and comps', () => {
    const tree = render(
      <ItemPriceSection
        priceEstimate={null}
        onWhyThisPrice={jest.fn()}
        q10="80"
        q50="120"
        q90="200"
        confidence="0.9"
        explanation="Strong market data"
        explanationExpanded={true}
        onToggleExplanation={jest.fn()}
        scarcityData={{
          scarcity_score: 9,
          listing_count: 1,
          supply_trend: 'declining',
        }}
        marketComps={[
          { title: 'Recent Sale', source: 'eBay', price: 130, currency: 'EUR' },
        ]}
        toNum={toNum}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// ItemNotesEditor
// ---------------------------------------------------------------------------

describe('ItemNotesEditor', () => {
  it('renders with minimal props and matches snapshot', () => {
    const tree = render(
      <ItemNotesEditor
        notes=""
        onChangeNotes={jest.fn()}
        onSaveNotes={jest.fn()}
        keyboardVisible={false}
        onFocus={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders Notes label', () => {
    render(
      <ItemNotesEditor
        notes=""
        onChangeNotes={jest.fn()}
        onSaveNotes={jest.fn()}
        keyboardVisible={false}
        onFocus={jest.fn()}
      />,
    );
    expect(screen.getByText('Notes')).toBeTruthy();
  });

  it('renders Save button when keyboard is visible', () => {
    render(
      <ItemNotesEditor
        notes="Some notes"
        onChangeNotes={jest.fn()}
        onSaveNotes={jest.fn()}
        keyboardVisible={true}
        onFocus={jest.fn()}
      />,
    );
    expect(screen.getByText('Save')).toBeTruthy();
  });

  it('does not render Save button when keyboard is hidden', () => {
    render(
      <ItemNotesEditor
        notes="Some notes"
        onChangeNotes={jest.fn()}
        onSaveNotes={jest.fn()}
        keyboardVisible={false}
        onFocus={jest.fn()}
      />,
    );
    expect(screen.queryByText('Save')).toBeNull();
  });

  it('matches snapshot with keyboard visible', () => {
    const tree = render(
      <ItemNotesEditor
        notes="Mint condition, purchased at local shop"
        onChangeNotes={jest.fn()}
        onSaveNotes={jest.fn()}
        keyboardVisible={true}
        onFocus={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
