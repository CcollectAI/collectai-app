/**
 * Snapshot tests for Skeleton loading components.
 * Catches unintended visual regressions in placeholder UI.
 */
import React from 'react';
import { render } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Snapshot Tests
// ---------------------------------------------------------------------------

describe('Skeleton snapshots', () => {
  it('matches snapshot with default props', () => {
    const tree = render(<Skeleton />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with custom dimensions', () => {
    const tree = render(<Skeleton width={200} height={40} borderRadius={12} />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonItemCard snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonItemCard />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonItemRow snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonItemRow />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonEventCard snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonEventCard />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonPortfolioHeader snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonPortfolioHeader />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonCategoryPills snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonCategoryPills />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonAnalytics snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonAnalytics />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonDeal snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonDeal />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonChat snapshot', () => {
  it('matches snapshot', () => {
    const tree = render(<SkeletonChat />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonGalleryGrid snapshot', () => {
  it('matches snapshot with default count', () => {
    const tree = render(<SkeletonGalleryGrid count={4} />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with 8 cells', () => {
    const tree = render(<SkeletonGalleryGrid count={8} />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});

describe('SkeletonList snapshots', () => {
  it('matches snapshot with row type', () => {
    const tree = render(<SkeletonList count={3} type="row" />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with card type', () => {
    const tree = render(<SkeletonList count={2} type="card" />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
