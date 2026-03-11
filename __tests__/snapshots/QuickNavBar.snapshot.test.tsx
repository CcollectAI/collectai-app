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

  it('matches snapshot with Items tab active', () => {
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
