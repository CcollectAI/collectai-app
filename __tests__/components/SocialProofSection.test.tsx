import React from 'react';
import { render } from '@testing-library/react-native';
import { SocialProofSection } from '@/components/SocialProofSection';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      background: '#fff',
      card: '#fff',
      text: '#000',
      muted: '#888',
      border: '#ddd',
      accent: '#40C9C6',
      warning: '#F59E0B',
      danger: '#DC2626',
      success: '#10B981',
    },
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
  recentListings: [],
  scarcity: { listingCount: 15, supplyTrend: 'decreasing' as const, scarcityScore: 0.7 },
};

const mockProofWithListings = {
  collectorCount: 0,
  isTrending: false,
  trendRank: null,
  recentSold: [],
  recentListings: [
    {
      title: 'Cowboy Bebop OST 1998',
      price: 89.5,
      currency: 'USD' as const,
      seenAt: '2026-04-18',
      source: 'discogs_listing',
      url: 'https://www.discogs.com/release/123',
    },
  ],
  scarcity: { listingCount: 0, supplyTrend: 'stable' as const, scarcityScore: 0 },
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
      recentListings: [],
      scarcity: { listingCount: 0, supplyTrend: 'stable' as const, scarcityScore: 0 },
    };
    const { toJSON } = render(
      <SocialProofSection socialProof={emptyProof} currency="EUR" />,
    );
    expect(toJSON()).toBeNull();
  });

  it('renders "List price" label and listing row when recentListings present', () => {
    const { getByText } = render(
      <SocialProofSection socialProof={mockProofWithListings} currency="EUR" />,
    );
    expect(getByText('List price')).toBeTruthy();
    expect(getByText('Currently Listed')).toBeTruthy();
    expect(getByText('Cowboy Bebop OST 1998')).toBeTruthy();
  });
});
