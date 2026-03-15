/**
 * Snapshot tests for QuickScan extracted components:
 * ScanFeedbackPanel, ScanSocialProof, ConditionGradeSelector.
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
    FEATURE_SCAN_FEEDBACK: true,
    FEATURE_SOCIAL_PROOF: true,
    FEATURE_CONDITION_GRADING: true,
  },
}));

jest.mock('../../src/api/collectorsApi', () => ({
  submitScanFeedback: jest.fn(),
}));

jest.mock('../../src/components/SocialProofSection', () => ({
  SocialProofSection: ({ socialProof }: any) => {
    const { Text } = require('react-native');
    return <Text>SocialProofSection: {socialProof?.collector_count ?? 0} collectors</Text>;
  },
}));

jest.mock('../../src/components/ConditionGradeSection', () => ({
  ConditionGradeSection: ({ defects, grade }: any) => {
    const { Text } = require('react-native');
    return (
      <Text>
        ConditionGradeSection: {grade?.grade ?? 'N/A'}, {defects?.length ?? 0} defects
      </Text>
    );
  },
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

// Import components after mocks
import { ScanFeedbackPanel } from '../../src/components/quickscan/ScanFeedbackPanel';
import { ScanSocialProof } from '../../src/components/quickscan/ScanSocialProof';
import { ConditionGradeSelector } from '../../src/components/quickscan/ConditionGradeSelector';

// ---------------------------------------------------------------------------
// ScanFeedbackPanel
// ---------------------------------------------------------------------------

describe('ScanFeedbackPanel', () => {
  it('renders with minimal props and matches snapshot', () => {
    const tree = render(
      <ScanFeedbackPanel
        name="Charizard Base Set"
        category="pokemon"
        feedbackEnabled={false}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders item name', () => {
    render(
      <ScanFeedbackPanel
        name="Pikachu VMAX"
        category="pokemon"
        feedbackEnabled={false}
      />,
    );
    expect(screen.getByText('Pikachu VMAX')).toBeTruthy();
  });

  it('renders category chip', () => {
    render(
      <ScanFeedbackPanel
        name="Test Item"
        category="hot_toys"
        feedbackEnabled={false}
      />,
    );
    expect(screen.getByText('Hot Toys')).toBeTruthy();
  });

  it('shows feedback hint when enabled with session ID', () => {
    render(
      <ScanFeedbackPanel
        name="Test"
        category="lego"
        feedbackEnabled={true}
        scanSessionId="sess-123"
      />,
    );
    expect(
      screen.getByText('Tap name, category, or condition to correct'),
    ).toBeTruthy();
  });

  it('renders condition chip when provided', () => {
    render(
      <ScanFeedbackPanel
        name="Test"
        category="pokemon"
        conditionGuess="near_mint"
        feedbackEnabled={false}
      />,
    );
    expect(screen.getByText('Near Mint')).toBeTruthy();
  });

  it('renders Unknown Item when name is empty', () => {
    render(
      <ScanFeedbackPanel
        name=""
        category="pokemon"
        feedbackEnabled={false}
      />,
    );
    expect(screen.getByText('Unknown Item')).toBeTruthy();
  });

  it('matches snapshot with feedback enabled', () => {
    const tree = render(
      <ScanFeedbackPanel
        name="Charizard"
        category="pokemon"
        conditionGuess="mint"
        scanSessionId="sess-abc"
        feedbackEnabled={true}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// ScanSocialProof
// ---------------------------------------------------------------------------

describe('ScanSocialProof', () => {
  it('renders null when socialProof is null', () => {
    const { toJSON } = render(
      <ScanSocialProof socialProof={null} currency="EUR" />,
    );
    expect(toJSON()).toBeNull();
  });

  it('renders when socialProof data is provided', () => {
    const proof = {
      collector_count: 42,
      trending: true,
      recent_sold: [],
      scarcity_score: 0.8,
    };
    const tree = render(
      <ScanSocialProof socialProof={proof as any} currency="EUR" />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// ConditionGradeSelector
// ---------------------------------------------------------------------------

describe('ConditionGradeSelector', () => {
  it('renders with grade data and matches snapshot', () => {
    const grade = { grade: 'NM', score: 8.5, service: 'PSA' };
    const tree = render(
      <ConditionGradeSelector
        defects={[]}
        grade={grade as any}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders with defects', () => {
    const grade = { grade: 'VG', score: 5.0, service: 'CGC' };
    const defects = [
      { type: 'scratch', severity: 'minor', location: 'front' },
    ];
    const tree = render(
      <ConditionGradeSelector
        defects={defects as any}
        grade={grade as any}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders with null grade', () => {
    const tree = render(
      <ConditionGradeSelector defects={[]} grade={null} />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
