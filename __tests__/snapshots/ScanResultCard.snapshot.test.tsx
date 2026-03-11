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
    scan_feedback_loop: true,
    social_proof: false,
    condition_grading: false,
  },
}));

jest.mock('../../src/components/SocialProofSection', () => ({
  SocialProofSection: () => null,
}));

jest.mock('../../src/components/ConditionGradeSection', () => ({
  ConditionGradeSection: () => null,
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
