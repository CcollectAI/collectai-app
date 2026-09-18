/**
 * Snapshot tests for QuickNavBar component.
 * Catches unintended visual regressions in the bottom navigation bar.
 */
import React from 'react';
import { render } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      card: '#FFFFFF',
      text: '#0F172A',
      muted: '#64748B',
      accent: '#81D8D0',
      border: '#E2E8F0',
    },
  }),
}));

jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 34, left: 0 }),
}));

const mockReplace = jest.fn();
let mockPathname = '/';

jest.mock('expo-router', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname,
}));

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: { CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT' },
}));

import { QuickNavBar } from '../../src/components/QuickNavBar';

// ---------------------------------------------------------------------------
// Snapshot Tests
// ---------------------------------------------------------------------------

describe('QuickNavBar snapshots', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockPathname = '/';
  });

  it('matches snapshot with no tab active', () => {
    mockPathname = '/some-other-screen';
    const tree = render(<QuickNavBar />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with Portfolio tab active', () => {
    mockPathname = '/(tabs)';
    const tree = render(<QuickNavBar />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  // Renamed 2026-09-18: there is no Items tab. QuickNavBar's five entries are
  // Portfolio, Market, Add, Events and Explore, so `/items/123` highlights
  // nothing — the case is still worth a snapshot (the bar overlays item detail
  // and must not claim a tab), but naming it for a tab that does not exist
  // made the suite look like it covered one.
  it('matches snapshot on an item detail route, which highlights no tab', () => {
    mockPathname = '/items/123';
    const tree = render(<QuickNavBar />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('matches snapshot with Marketplace tab active', () => {
    mockPathname = '/marketplace/search';
    const tree = render(<QuickNavBar />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
