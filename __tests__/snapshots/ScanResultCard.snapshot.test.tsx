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

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
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
    },
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

jest.mock('react-native-view-shot', () => {
  const { View } = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: React.forwardRef((props: any, ref: any) => <View {...props} ref={ref} />),
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

jest.mock('../../src/components/quickscan/ShareCard', () => ({
  ShareCard: () => null,
}));

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
        imageUrl: 'https://example.com/alt.jpg',
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
