/**
 * Analytics component tests.
 *
 * Covers PortfolioTierBadge, WinnersLosersSection, and PredictionAccuracySection.
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
};

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: mockColors, isDark: false }),
}));

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: { hapticsEnabled: true, currency: 'EUR', isDark: false },
    updateSettings: jest.fn(),
  }),
}));

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
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

jest.mock('../../src/components/ScoreExplanationSheet', () => ({
  ScoreExplanationSheet: () => null,
}));

jest.mock('../../src/analytics/portfolioMetrics', () => ({}));

jest.mock('../../src/theme/tokens', () => ({
  radius: { md: 12, xl: 24, sm: 8, lg: 16 },
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
}));

jest.mock('../../src/lib/format', () => ({
  formatPrice: (price: number, currency: string) => `${currency} ${price}`,
}));

jest.mock('../../src/lib/timeAgo', () => ({
  timeAgo: (date: string) => '2h ago',
}));

// Now import components after mocks
import { PortfolioTierBadge } from '../../src/components/analytics/PortfolioTierBadge';
import { WinnersLosersSection } from '../../src/components/analytics/WinnersLosersSection';
import { PredictionAccuracySection } from '../../src/components/analytics/PredictionAccuracySection';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTierSummary(tier: string, scores?: Partial<{ rarityScore: number; completenessScore: number; diversificationScore: number }>) {
  return {
    tier,
    rarityScore: scores?.rarityScore ?? 0.85,
    completenessScore: scores?.completenessScore ?? 0.72,
    diversificationScore: scores?.diversificationScore ?? 0.60,
  };
}

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'item-1',
    name: 'Charizard Base Set',
    category: 'pokemon',
    quantity: 1,
    currentValue: 350,
    change1dPct: 0.05,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// PortfolioTierBadge
// ---------------------------------------------------------------------------

describe('PortfolioTierBadge', () => {
  it('renders Diamond tier label', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Diamond')} />);
    expect(screen.getByText('Diamond')).toBeTruthy();
  });

  it('renders Gold tier label', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Gold')} />);
    expect(screen.getByText('Gold')).toBeTruthy();
  });

  it('renders Silver tier label', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Silver')} />);
    expect(screen.getByText('Silver')).toBeTruthy();
  });

  it('displays Portfolio Tier card title', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Diamond')} />);
    expect(screen.getByText('Portfolio Tier')).toBeTruthy();
  });

  it('displays rarity, completeness, and diversity scores', () => {
    render(
      <PortfolioTierBadge
        tierSummary={makeTierSummary('Diamond', {
          rarityScore: 0.85,
          completenessScore: 0.72,
          diversificationScore: 0.60,
        })}
      />,
    );
    expect(screen.getByText('85')).toBeTruthy();
    expect(screen.getByText('72')).toBeTruthy();
    expect(screen.getByText('60')).toBeTruthy();
  });

  it('renders score labels', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Gold')} />);
    expect(screen.getByText('Rarity')).toBeTruthy();
    expect(screen.getByText('Completeness')).toBeTruthy();
    expect(screen.getByText('Diversity')).toBeTruthy();
  });

  it('has leaderboard accessibility label', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Gold')} />);
    expect(
      screen.getByLabelText('Gold tier \u2014 view leaderboard'),
    ).toBeTruthy();
  });

  it('matches snapshot for Diamond tier', () => {
    const tree = render(
      <PortfolioTierBadge tierSummary={makeTierSummary('Diamond')} />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// WinnersLosersSection
// ---------------------------------------------------------------------------

describe('WinnersLosersSection', () => {
  it('returns null when both winners and losers are empty', () => {
    const { toJSON } = render(
      <WinnersLosersSection winners={[]} losers={[]} />,
    );
    expect(toJSON()).toBeNull();
  });

  it('renders the Movers title', () => {
    render(
      <WinnersLosersSection
        winners={[makeItem({ id: 'w1', name: 'Winner Item', change1dPct: 0.1 })]}
        losers={[]}
      />,
    );
    expect(screen.getByText('Movers')).toBeTruthy();
  });

  it('renders winner items', () => {
    render(
      <WinnersLosersSection
        winners={[
          makeItem({ id: 'w1', name: 'Alpha Card', change1dPct: 0.10 }),
          makeItem({ id: 'w2', name: 'Beta Card', change1dPct: 0.05 }),
        ]}
        losers={[]}
      />,
    );
    expect(screen.getByText('Alpha Card')).toBeTruthy();
    expect(screen.getByText('Beta Card')).toBeTruthy();
    expect(screen.getByText('Winners')).toBeTruthy();
  });

  it('renders loser items', () => {
    render(
      <WinnersLosersSection
        winners={[]}
        losers={[
          makeItem({ id: 'l1', name: 'Declining Asset', change1dPct: -0.08 }),
        ]}
      />,
    );
    expect(screen.getByText('Declining Asset')).toBeTruthy();
    expect(screen.getByText('Losers')).toBeTruthy();
  });

  it('displays percentage change text', () => {
    render(
      <WinnersLosersSection
        winners={[makeItem({ id: 'w1', name: 'Gainer', change1dPct: 0.1234 })]}
        losers={[]}
      />,
    );
    expect(screen.getByText('+12.34%')).toBeTruthy();
  });

  it('limits display to 3 items per section', () => {
    const winners = Array.from({ length: 5 }, (_, i) =>
      makeItem({ id: `w${i}`, name: `Winner ${i}`, change1dPct: 0.1 }),
    );
    render(<WinnersLosersSection winners={winners} losers={[]} />);
    expect(screen.getByText('Winner 0')).toBeTruthy();
    expect(screen.getByText('Winner 2')).toBeTruthy();
    expect(screen.queryByText('Winner 3')).toBeNull();
  });

  it('matches snapshot with winners and losers', () => {
    const tree = render(
      <WinnersLosersSection
        winners={[makeItem({ id: 'w1', name: 'Up Item', change1dPct: 0.05 })]}
        losers={[makeItem({ id: 'l1', name: 'Down Item', change1dPct: -0.03 })]}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// PredictionAccuracySection
// ---------------------------------------------------------------------------

describe('PredictionAccuracySection', () => {
  it('returns null when data is empty', () => {
    const { toJSON } = render(<PredictionAccuracySection data={[]} />);
    expect(toJSON()).toBeNull();
  });

  it('renders Prediction Accuracy title', () => {
    render(
      <PredictionAccuracySection
        data={[{ category: 'pokemon', mae: 5.0, mape: 0.12, r2: 0.85 }]}
      />,
    );
    expect(screen.getByText('Prediction Accuracy')).toBeTruthy();
  });

  it('renders category name with underscores replaced', () => {
    render(
      <PredictionAccuracySection
        data={[{ category: 'hot_toys', mae: 3.0, mape: 0.08, r2: 0.90 }]}
      />,
    );
    expect(screen.getByText('hot toys')).toBeTruthy();
  });

  it('renders MAPE and R-squared values', () => {
    render(
      <PredictionAccuracySection
        data={[{ category: 'lego', mae: 2.5, mape: 0.15, r2: 0.78 }]}
      />,
    );
    expect(screen.getByText('15.0%')).toBeTruthy();
    expect(screen.getByText('0.78')).toBeTruthy();
  });

  it('renders column headers', () => {
    render(
      <PredictionAccuracySection
        data={[{ category: 'funko', mae: 1, mape: 0.1, r2: 0.9 }]}
      />,
    );
    expect(screen.getByText('Category')).toBeTruthy();
    expect(screen.getByText('MAPE')).toBeTruthy();
    // R-squared header
    expect(screen.getByText('R\u00B2')).toBeTruthy();
  });

  it('limits display to 8 categories', () => {
    const data = Array.from({ length: 10 }, (_, i) => ({
      category: `cat_${i}`,
      mae: 1,
      mape: 0.1,
      r2: 0.8,
    }));
    render(<PredictionAccuracySection data={data} />);
    expect(screen.getByText('cat 7')).toBeTruthy();
    expect(screen.queryByText('cat 8')).toBeNull();
  });

  it('matches snapshot with multiple categories', () => {
    const tree = render(
      <PredictionAccuracySection
        data={[
          { category: 'pokemon', mae: 5, mape: 0.12, r2: 0.85 },
          { category: 'lego', mae: 3, mape: 0.08, r2: 0.92 },
        ]}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
