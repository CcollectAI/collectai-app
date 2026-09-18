/**
 * Snapshot tests for Marketplace extracted components:
 * RegionalInsightsSection.
 *
 * The DemandHeatBanner half was removed 2026-09-18: that component went with
 * the market hub in `b15d936` ("Dissolve the market hub"), and its import kept
 * this whole file from running — so RegionalInsightsSection, which is still on
 * screen, was untested while the suite looked like it covered both.
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
import {
  RegionalInsightsSection,
  type RegionalDemandItem,
} from '../../src/components/marketplace/RegionalInsightsSection';

// ---------------------------------------------------------------------------
// RegionalInsightsSection
// ---------------------------------------------------------------------------

describe('RegionalInsightsSection', () => {
  const sampleItems: RegionalDemandItem[] = [
    {
      item_key: 'charizard-base-set',
      category: 'pokemon',
      signal_count: 42,
      region: 'Europe',
    },
    {
      item_key: 'lego-star-wars',
      category: 'lego',
      signal_count: 28,
      region: 'North America',
    },
  ];

  it('renders null when items array is empty', () => {
    const { toJSON } = render(
      <RegionalInsightsSection items={[]} onSearchItem={jest.fn()} />,
    );
    expect(toJSON()).toBeNull();
  });

  it('renders with sample data and matches snapshot', () => {
    const tree = render(
      <RegionalInsightsSection items={sampleItems} onSearchItem={jest.fn()} />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders section title', () => {
    render(
      <RegionalInsightsSection items={sampleItems} onSearchItem={jest.fn()} />,
    );
    expect(screen.getByText(/Popular in Your Region/)).toBeTruthy();
  });

  it('renders item keys as titles', () => {
    render(
      <RegionalInsightsSection items={sampleItems} onSearchItem={jest.fn()} />,
    );
    expect(screen.getByText('charizard base set')).toBeTruthy();
    expect(screen.getByText('lego star wars')).toBeTruthy();
  });

  it('renders region metadata', () => {
    render(
      <RegionalInsightsSection items={sampleItems} onSearchItem={jest.fn()} />,
    );
    expect(screen.getByText(/Europe/)).toBeTruthy();
    expect(screen.getByText(/North America/)).toBeTruthy();
  });

  it('renders signal counts', () => {
    render(
      <RegionalInsightsSection items={sampleItems} onSearchItem={jest.fn()} />,
    );
    expect(screen.getByText('42')).toBeTruthy();
    expect(screen.getByText('28')).toBeTruthy();
  });
});
