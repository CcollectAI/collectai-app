/**
 * The offline banner is a pill ABOVE the bottom bar, not an overlay across the
 * header (OPEN_DECISIONS #10, 2026-09-27: it hid back, bell, inbox, settings).
 */
import React from 'react';
import { render } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';
jest.mock('@/hooks/useNetworkStatus', () => ({ useNetworkStatus: () => ({ isOnline: false }) }));
jest.mock('@/lib/mutationQueue', () => ({ getQueueLength: () => 2 }));
jest.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }) }));
import { OfflineBanner, offlinePillBottom } from '../../src/components/OfflineBanner';
import { EXTERNAL_TAB_BAR_HEIGHT } from '../../src/components/ExternalTabBar';

it('sits above the bottom bar on a notched and a flat phone', () => {
  // Both bars are EXTERNAL_TAB_BAR_HEIGHT + max(insets.bottom, 10) tall.
  expect(offlinePillBottom(34)).toBeGreaterThan(EXTERNAL_TAB_BAR_HEIGHT + 34);
  expect(offlinePillBottom(0)).toBeGreaterThan(EXTERNAL_TAB_BAR_HEIGHT + 10);
});

it('is anchored to the bottom, never the top, and says how much is queued', () => {
  const { getByText, getByLabelText } = render(<OfflineBanner />);
  expect(getByText("You're offline — 2 changes queued")).toBeTruthy();
  const flat = StyleSheet.flatten(getByLabelText(/You're offline/).props.style);
  expect(flat.bottom).toBe(offlinePillBottom(34));
  expect(flat.top).toBeUndefined();
});
