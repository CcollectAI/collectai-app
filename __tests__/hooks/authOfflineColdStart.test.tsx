/**
 * Offline cold start must not read as "signed out" (2026-09-26).
 *
 * Walked on Android with the network off: getSession() timed out at 8 s (GoTrue
 * was retrying an expired token's refresh), AuthProvider ended loading with
 * user=null, and the root gate sent a signed-in member to the login screen —
 * then yanked them into the app ~20 s later when INITIAL_SESSION (session=yes)
 * arrived. A timed-out read now waits for that first event, with a ceiling.
 */
import React from 'react';
import { render, act } from '@testing-library/react-native';

let emit: ((event: string, session: unknown) => void) | null = null;
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => new Promise(() => {}), // offline: never settles in time
      startAutoRefresh: jest.fn(),
      stopAutoRefresh: jest.fn(),
      refreshSession: jest.fn().mockResolvedValue({}),
      onAuthStateChange: (cb: (e: string, s: unknown) => void) => {
        emit = cb;
        return { data: { subscription: { unsubscribe: () => {} } } };
      },
    },
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle: () => new Promise(() => {}) }) }) }),
  },
}));
jest.mock('../../src/data/offlineCache', () => ({ bindCacheOwner: jest.fn().mockResolvedValue(false) }));
jest.mock('../../src/data/providers/userProvider', () => ({ clearProfileCache: jest.fn() }));
jest.mock('../../src/lib/referral', () => ({ captureReferralFromUrl: jest.fn() }));
jest.mock('../../src/auth/recoveryState', () => ({ setRecoveryPending: jest.fn() }));
jest.mock('../../src/analytics/track', () => ({ identifyUser: jest.fn(), resetAnalytics: jest.fn(), track: jest.fn() }));
jest.mock('../../src/lib/purchases', () => ({
  initPurchases: jest.fn(),
  identifyUser: jest.fn().mockResolvedValue(undefined),
  setReferralAttribute: jest.fn(),
}));
jest.mock('../../src/lib/logger', () => ({ logger: { error: jest.fn(), warn: jest.fn(), info: jest.fn(), debug: jest.fn() } }));
jest.mock('expo-linking', () => ({
  getInitialURL: jest.fn().mockResolvedValue(null),
  addEventListener: () => ({ remove: () => {} }),
}));
jest.mock('expo-router', () => ({ router: { replace: jest.fn(), push: jest.fn() } }));

import { AuthProvider } from '../../src/providers/AuthProvider';
import { useAuthContext } from '../../src/providers/useAuthContext';

let seen: { loading: boolean; userId: string | null } = { loading: true, userId: null };
function Probe() {
  const { loading, user } = useAuthContext();
  seen = { loading, userId: user?.id ?? null };
  return null;
}

beforeEach(() => {
  jest.useFakeTimers();
  emit = null;
});
afterEach(() => jest.useRealTimers());

it('a timed-out session read keeps loading until the first auth event', async () => {
  render(<AuthProvider><Probe /></AuthProvider>);
  await act(async () => { jest.advanceTimersByTime(9_000); });
  expect(seen.loading).toBe(true); // was: false with user=null → the login screen

  await act(async () => { emit?.('INITIAL_SESSION', { user: { id: 'u1' }, expires_at: 1 }); });
  expect(seen).toEqual({ loading: false, userId: 'u1' });
});

it('does not wait forever: the ceiling ends loading', async () => {
  render(<AuthProvider><Probe /></AuthProvider>);
  await act(async () => { jest.advanceTimersByTime(9_000); });
  expect(seen.loading).toBe(true);
  await act(async () => { jest.advanceTimersByTime(46_000); });
  expect(seen.loading).toBe(false);
});
