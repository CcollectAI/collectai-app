/**
 * Snapshot tests for ScanResultCard component.
 * Catches unintended visual regressions in the scan result layout.
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
    FEATURE_DUPLICATE_DETECTION: false,
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

import { ScanResultCard } from '../../src/components/ScanResultCard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScanResult(overrides: Partial<QuickScanResult> = {}): QuickScanResult {
  return {
    attributes: {
      category: 'pokemon',
      editionGuess: 'Base Set',
      conditionGuess: 'Near Mint',
      rarityScore: 0.9,
    },
    prediction: {
      name: 'Charizard Base Set Holo',
      estimatedLow: 200,
      estimatedMid: 350,
      estimatedHigh: 500,
      currency: 'USD',
      confidence: 0.87,
      explanation: 'Based on recent eBay sales',
    },
    ...overrides,
  };
}

const noopFn = () => {};

// ---------------------------------------------------------------------------
// Snapshot Tests
// ---------------------------------------------------------------------------

describe('ScanResultCard snapshots', () => {
  it('matches snapshot with full scan result', () => {
    const tree = render(
      <ScanResultCard
        scanResult={makeScanResult()}
        capturedUri="file:///photo.jpg"
        currency="USD"
        onRetake={noopFn}
        onSelectAlternative={noopFn}
        onConfirm={noopFn}
      />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with catalog alternatives', () => {
    const alternatives: CatalogAlternative[] = [
      {
        catalogItemId: 'cat-1',
        itemKey: 'charizard-shadowless',
        title: 'Charizard Shadowless',
        category: 'pokemon',
        brand: null,
        rarity: 'Holo Rare',
        setCode: 'base1',
        hasReferenceImage: true,
        matchScore: 0.82,
        matchReason: 'Similar card variant',
      },
    ];
    const tree = render(
      <ScanResultCard
        scanResult={makeScanResult({ alternatives })}
        capturedUri="file:///photo.jpg"
        currency="USD"
        onRetake={noopFn}
        onSelectAlternative={noopFn}
        onConfirm={noopFn}
      />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with low confidence', () => {
    const tree = render(
      <ScanResultCard
        scanResult={makeScanResult({
          prediction: {
            name: 'Unknown Card',
            estimatedLow: 5,
            estimatedMid: 10,
            estimatedHigh: 20,
            currency: 'USD',
            confidence: 0.3,
          },
        })}
        capturedUri="file:///photo.jpg"
        currency="EUR"
        onRetake={noopFn}
        onSelectAlternative={noopFn}
        onConfirm={noopFn}
      />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
