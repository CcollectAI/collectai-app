import React from 'react';
import { render } from '@testing-library/react-native';
import { SocialProofSection } from '@/components/SocialProofSection';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: { background: '#fff', card: '#fff', text: '#000', muted: '#888', border: '#ddd' },
  }),
}));

jest.mock('@/lib/format', () => ({
  formatPrice: (val: number, cur: string) => `${cur} ${val.toFixed(2)}`,
}));

const mockProof = {
  collectorCount: 42,
  isTrending: true,
  trendRank: 3,
  recentSold: [
    { title: 'Charizard Base Set', price: 500, currency: 'USD' as const, soldAt: '2025-01-01', source: 'ebay' },
  ],
  scarcity: { listingCount: 15, supplyTrend: 'decreasing' as const, scarcityScore: 0.7 },
};

describe('SocialProofSection', () => {
  it('renders collector count', () => {
    const { getByText } = render(
      <SocialProofSection socialProof={mockProof} currency="EUR" />,
    );
    expect(getByText('42 collectors')).toBeTruthy();
  });

  it('renders trending badge', () => {
    const { getByText } = render(
      <SocialProofSection socialProof={mockProof} currency="EUR" />,
    );
    expect(getByText('Trending #3')).toBeTruthy();
  });

  it('renders recent sold items', () => {
    const { getByText } = render(
      <SocialProofSection socialProof={mockProof} currency="EUR" />,
    );
    expect(getByText('Charizard Base Set')).toBeTruthy();
  });

  it('returns null when no data', () => {
    const emptyProof = {
      collectorCount: 0,
      isTrending: false,
      trendRank: null,
      recentSold: [],
      scarcity: { listingCount: 0, supplyTrend: 'stable' as const, scarcityScore: 0 },
    };
    const { toJSON } = render(
      <SocialProofSection socialProof={emptyProof} currency="EUR" />,
    );
    expect(toJSON()).toBeNull();
  });
});
