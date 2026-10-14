/**
 * ScanResultCard — "Where to buy" and "Sell yours" (2026-10-14).
 * Mocks copied from the snapshot test (same reasons, see there).
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import type { QuickScanResult, CatalogAlternative } from '../../src/data/types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mocking a MODULE replaces all of it, so every export the component uses has
// to be here. ScanResultCard gained `useScannerTheme` after this test was last
// able to run, and a partial module mock fails as "not a function" rather than
// as a missing mock — which reads like a component bug.
//
// Shaped like the real one (src/theme/useAppTheme.ts): scanner theme is the
// base theme with a dark palette and `isDark: true`. Returning the light colours
// here would snapshot a card that never renders in the app.
const __themeColors = () => ({
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  background: '#F7FAF9',
  accent: '#81D8D0',
  border: '#E2E8F0',
  skeleton: '#E2E8F0',
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
  brand: { base: '#81D8D0', dark: '#5FBFB6' },
  accentText: '#FFFFFF',
});

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: __themeColors(), isDark: false }),
  useScannerTheme: () => ({
    colors: __themeColors(),
    status: { success: '#10B981', warning: '#F59E0B', error: '#EF4444', info: '#3B82F6' },
    isDark: true,
  }),
}));

jest.mock('react-native-svg', () => {
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: (props: any) => <View testID="svg" {...props} />,
    Circle: (props: any) => <View testID="svg-circle" {...props} />,
  };
});

jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => <Pressable {...props} />,
  };
});

jest.mock('../../src/lib/format', () => ({
  formatPrice: (value: number, currency: string) => `$${value}`,
}));

jest.mock('../../src/config/featureFlags', () => ({
  featureFlags: {
    FEATURE_SCAN_FEEDBACK: true,
    FEATURE_SOCIAL_PROOF: false,
    FEATURE_CONDITION_GRADING: false,
    FEATURE_DUPLICATE_DETECTION: true,
  },
}));

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
  },
}));

jest.mock('../../src/analytics/track', () => ({
  track: jest.fn(),
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/constants/colors', () => ({
  BRAND_COLORS: { tiffany: '#81D8D0' },
}));

jest.mock('../../src/components/quickscan/ScanSocialProof', () => ({
  ScanSocialProof: () => null,
}));

jest.mock('../../src/components/quickscan/ConditionGradeSelector', () => ({
  ConditionGradeSelector: () => null,
}));

jest.mock('../../src/components/quickscan/ScanFeedbackPanel', () => ({
  ScanFeedbackPanel: () => null,
}));

// ShareCard was removed entirely in 69c4224, but this mock outlived it. Because
// jest.mock() resolves the path eagerly, a mock of a deleted module takes the
// WHOLE suite down — so the ScanResultCard snapshots this file exists for have
// not run since that commit. Same shape as the react-native-view-shot mock
// removed alongside it: a mock is a dependency, and a dependency that no longer
// exists is a broken import wearing a test's clothes.

jest.mock('../../src/api/collectorsApi', () => ({
  submitScanFeedback: jest.fn(),
}));

import { fireEvent } from '@testing-library/react-native';
import { ScanResultCard } from '../../src/components/ScanResultCard';

const base: QuickScanResult = {
  attributes: { category: 'pokemon', editionGuess: 'Base Set', conditionGuess: 'Near Mint', rarityScore: 0.9 },
  prediction: { name: 'Charizard Base Set Holo', estimatedLow: 200, estimatedMid: 350, estimatedHigh: 500,
    currency: 'EUR', confidence: 0.87 },
};
const links = [
  { source: 'ebay', url: 'https://www.ebay.com/sch/i.html?_nkw=x', affiliate_url: 'https://www.ebay.com/sch/i.html?_nkw=x&campid=1', label: 'eBay' },
  { source: 'cardmarket', url: 'https://www.cardmarket.com/x', affiliate_url: '', label: 'Cardmarket' },
];
const card = (props: Record<string, unknown>, result: QuickScanResult = base) => render(
  <ScanResultCard scanResult={result} capturedUri="file:///p.jpg" currency="EUR"
    onRetake={() => {}} onSelectAlternative={() => {}} onConfirm={() => {}} {...props} />,
);

describe('ScanResultCard — where to buy', () => {
  it('lists the shops and opens the one tapped', () => {
    const open = jest.fn();
    const r = card({ shopLinks: links, onOpenShopLink: open });
    expect(r.getByText('Where to buy')).toBeTruthy();
    fireEvent.press(r.getByText('Cardmarket'));
    expect(open).toHaveBeenCalledWith(links[1]);
  });

  it.each([['loading', undefined], ['failed', null], ['none', []]])(
    'renders no section while %s', (_label, value) => {
      const r = card({ shopLinks: value, onOpenShopLink: jest.fn() });
      expect(r.queryByText('Where to buy')).toBeNull();
    });
});

describe('ScanResultCard — sell yours', () => {
  const owned: QuickScanResult = { ...base,
    duplicateInfo: { ownedCount: 1, ownedItemIds: ['item-1'], isVariant: false, variantOf: null, setCompletion: null } };

  it('offers Sell yours when the scan matched an owned item', () => {
    const sell = jest.fn();
    const r = card({ onSellOwned: sell }, owned);
    fireEvent.press(r.getByText('Sell yours'));
    expect(sell).toHaveBeenCalledTimes(1);
  });

  it('does not offer it without a handler', () => {
    expect(card({}, owned).queryByText('Sell yours')).toBeNull();
  });
});
