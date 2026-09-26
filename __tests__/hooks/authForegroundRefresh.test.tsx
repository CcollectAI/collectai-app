/**
 * Returning to the foreground refreshes the token only when it is near expiry
 * (2026-09-26). It refreshed on EVERY foreground — every app switch and deep
 * link — and each refresh held GoTrue's lock through a multi-second secure-store
 * write, sending requests out tokenless into a 401 → refresh-again storm.
 */
import React from 'react';
import { render, act } from '@testing-library/react-native';

let mockExpiresAt = 0;
const mockRefresh = jest.fn().mockResolvedValue({ data: {}, error: null });
const mockStart = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: { user: { id: 'u1' }, expires_at: mockExpiresAt } }, error: null }),
      startAutoRefresh: (...a: unknown[]) => mockStart(...a),
      stopAutoRefresh: jest.fn(),
      refreshSession: (...a: unknown[]) => mockRefresh(...a),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
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
import { AppState } from 'react-native';

// The jest RN preset's AppState.currentState is a mock FUNCTION, not 'active',
// so without this the foreground branch never runs and the "no refresh" test
// passes vacuously (it did, on the first version of this file).
beforeAll(() => {
  Object.defineProperty(AppState, 'currentState', { value: 'active', configurable: true });
});

const nowS = () => Math.floor(Date.now() / 1000);

beforeEach(() => mockRefresh.mockClear());

it('does not refresh a fresh token on foreground', async () => {
  mockExpiresAt = nowS() + 55 * 60; // 55 min left
  render(<AuthProvider>{null}</AuthProvider>);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mockStart).toHaveBeenCalled(); // proves the foreground branch ran
  expect(mockRefresh).not.toHaveBeenCalled();
});

it('refreshes a token that is about to expire', async () => {
  mockExpiresAt = nowS() + 2 * 60; // 2 min left
  render(<AuthProvider>{null}</AuthProvider>);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mockRefresh).toHaveBeenCalledTimes(1);
});
