/**
 * Analytics component tests.
 *
 * Covers PortfolioTierBadge and PredictionAccuracySection.
 *
 * The WinnersLosersSection block was removed 2026-09-18: that component was
 * deleted as an orphan in `65ea3ee` ("delete three orphans, after checking
 * whether any was worth keeping"), and the import kept the whole suite from
 * running — so the two components that DO exist were untested for as long as
 * the file looked like it covered three.
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
  brand: { base: '#81D8D0', dark: '#5FBFB6', darker: '#44A9A1', light: '#AEE6E1', lighter: '#E6F7F5' },
  skeleton: '#E2E8F0',
  chartLine: '#40C9C6',
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
import { PredictionAccuracySection } from '../../src/components/analytics/PredictionAccuracySection';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * TYPED as `PortfolioTierSummary`, not `{ tier: string, ... }`.
 *
 * It used to be loosely typed, so when the summary gained its coverage fields
 * on 2026-09-21 `tsc` stayed green and all eight of these blew up at RUNTIME
 * instead. A test helper that does not commit to the real type cannot tell you
 * the real type moved.
 *
 * Note what these tests can and cannot prove: they render a summary handed to
 * them, so they check the BADGE. They say nothing about whether the tier can
 * be earned — that is `__tests__/analytics/portfolioTier.test.ts`, and its
 * absence is why "Unranked for every account" survived five weeks of green.
 */
function makeTierSummary(
  tier: Tier,
  scores?: Partial<Omit<PortfolioTierSummary, 'tier'>>,
): PortfolioTierSummary {
  return {
    tier,
    rarityScore: scores?.rarityScore ?? 0.85,
    completenessScore: scores?.completenessScore ?? 0.72,
    diversificationScore: scores?.diversificationScore ?? 0.60,
    rarityCoverage: scores?.rarityCoverage ?? { known: 40, total: 40 },
    completenessCoverage: scores?.completenessCoverage ?? { known: 3, total: 3 },
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

  // The badge branches on BETA_MODE || COMMUNITY_GATED: while community
  // features are gated the leaderboard is hidden, and the badge renders
  // NON-TAPPABLE so we do not dangle a tap hint that goes nowhere
  // (project_community_gated_flag).
  //
  // This test asserted the tappable branch and had been failing since the gate
  // went in — a stale test reporting a bug that is not there.
  it('is NOT tappable while community features are gated', () => {
    render(<PortfolioTierBadge tierSummary={makeTierSummary('Gold')} />);
    expect(screen.queryByLabelText('Gold tier \u2014 view leaderboard')).toBeNull();
    expect(screen.queryByText('Tap to view leaderboard')).toBeNull();
    // The tier itself must still render — gating hides the ACTION, not the badge.
    expect(screen.getByText('Gold')).toBeTruthy();
  });

  // The UNGATED branch is deliberately not tested. BETA_MODE and
  // COMMUNITY_GATED are module-level constants read at import time, so
  // exercising the other branch needs a module-registry reset that fights the
  // '@/' alias — and a test I cannot make reliable is worse than none. When the
  // gate is lifted the assertion above will fail loudly, which is the signal
  // that matters.

  it('matches snapshot for Diamond tier', () => {
    const tree = render(
      <PortfolioTierBadge tierSummary={makeTierSummary('Diamond')} />,
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

  it('renders the curated category name, not the de-underscored slug', () => {
    // Renamed and re-pointed 2026-09-18. This asserted `'hot toys'` — the
    // old behaviour, a bare `replace(/_/g, ' ')`. The section now goes through
    // `categoryDisplayName`, so a known slug gets its curated name. The test
    // was pinning lowercase slug text on screen, which is the defect the
    // category vocabulary exists to prevent.
    //
    // `lorcana`, not `hot_toys`: title-casing `hot_toys` produces "Hot Toys",
    // which is ALSO its curated name, so that fixture passes whether the
    // vocabulary is consulted or not — a test that cannot fail. Proven by
    // mutation: with the `CATEGORY_SLUG_TO_NAME` lookup disabled, the
    // `hot_toys` version stayed green. `lorcana` → "Disney Lorcana" can only
    // come from the table.
    render(
      <PredictionAccuracySection
        data={[{ category: 'lorcana', mae: 3.0, mape: 0.08, r2: 0.90 }]}
      />,
    );
    expect(screen.getByText('Disney Lorcana')).toBeTruthy();
  });

  it('title-cases an UNKNOWN slug rather than printing it raw', () => {
    // The other branch of `categoryDisplayName`: no curated name, so it must
    // still not reach the member underscored or lowercased.
    render(
      <PredictionAccuracySection
        data={[{ category: 'some_new_thing', mae: 1, mape: 0.1, r2: 0.8 }]}
      />,
    );
    expect(screen.getByText('Some New Thing')).toBeTruthy();
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
    // 'Cat 7' / 'Cat 8', title-cased by `categoryDisplayName`; the lowercase
    // spellings this used to assert are the pre-vocabulary output.
    expect(screen.getByText('Cat 7')).toBeTruthy();
    expect(screen.queryByText('Cat 8')).toBeNull();
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
