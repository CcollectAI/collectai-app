import React from 'react';
import { render, screen } from '@testing-library/react-native';

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      skeleton: '#E2E8F0',
      card: '#FFFFFF',
      background: '#F7FAF9',
      text: '#0F172A',
      muted: '#64748B',
    },
  }),
}));

import {
  Skeleton,
  SkeletonItemCard,
  SkeletonItemRow,
  SkeletonEventCard,
  SkeletonPortfolioHeader,
  SkeletonCategoryPills,
  SkeletonAnalytics,
  SkeletonDeal,
  SkeletonChat,
  SkeletonGalleryGrid,
  SkeletonList,
} from '../../src/components/Skeleton';

describe('Skeleton', () => {
  it('renders without crashing', () => {
    expect(() => render(<Skeleton />)).not.toThrow();
  });

  it('renders with custom dimensions', () => {
    expect(() => render(<Skeleton width={200} height={40} />)).not.toThrow();
  });

  it('renders with custom borderRadius', () => {
    expect(() => render(<Skeleton borderRadius={12} />)).not.toThrow();
  });

  it('has accessibility label "Loading"', () => {
    render(<Skeleton />);
    expect(screen.getByLabelText('Loading')).toBeTruthy();
  });
});

describe('SkeletonList', () => {
  it('renders the specified count of items', () => {
    render(<SkeletonList count={3} type="row" />);
    const items = screen.getAllByLabelText('Loading');
    expect(items.length).toBeGreaterThanOrEqual(3);
  });

  it('renders card type items', () => {
    render(<SkeletonList count={2} type="card" />);
    const items = screen.getAllByLabelText('Loading');
    expect(items.length).toBeGreaterThanOrEqual(2);
  });
});

describe('SkeletonGalleryGrid', () => {
  it('renders specified number of cells', () => {
    render(<SkeletonGalleryGrid count={4} />);
    const items = screen.getAllByLabelText('Loading');
    expect(items.length).toBeGreaterThanOrEqual(4);
  });
});

describe('Composite skeleton variants (smoke tests)', () => {
  it('SkeletonItemCard renders without error', () => {
    expect(() => render(<SkeletonItemCard />)).not.toThrow();
  });

  it('SkeletonItemRow renders without error', () => {
    expect(() => render(<SkeletonItemRow />)).not.toThrow();
  });

  it('SkeletonEventCard renders without error', () => {
    expect(() => render(<SkeletonEventCard />)).not.toThrow();
  });

  it('SkeletonPortfolioHeader renders without error', () => {
    expect(() => render(<SkeletonPortfolioHeader />)).not.toThrow();
  });

  it('SkeletonCategoryPills renders without error', () => {
    expect(() => render(<SkeletonCategoryPills />)).not.toThrow();
  });

  it('SkeletonAnalytics renders without error', () => {
    expect(() => render(<SkeletonAnalytics />)).not.toThrow();
  });

  it('SkeletonDeal renders without error', () => {
    expect(() => render(<SkeletonDeal />)).not.toThrow();
  });

  it('SkeletonChat renders without error', () => {
    expect(() => render(<SkeletonChat />)).not.toThrow();
  });
});
