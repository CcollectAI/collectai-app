/**
 * A Pro member must not meet the free gate on every screen mount (2026-09-26).
 * Each useBillingLimits() started on free and refetched, so the catalogue page
 * showed "Sparrow Pro" upsells to a paying account until the round trip landed.
 */
import React from 'react';
import { renderHook, waitFor } from '@testing-library/react-native';

const mockGetBillingStatus = jest.fn();
jest.mock('../../src/api/collectorsApi', () => ({
  getBillingStatus: (...a: unknown[]) => mockGetBillingStatus(...a),
}));
jest.mock('../../src/lib/purchases', () => ({
  addCustomerInfoUpdateListener: () => () => {},
  getCustomerInfo: jest.fn().mockResolvedValue(null),
  isPurchasesAvailable: () => false,
  planFromCustomerInfo: () => 'free',
}));
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: { getItem: jest.fn().mockResolvedValue(null), setItem: jest.fn() },
}));
jest.mock('../../src/lib/logger', () => ({ logger: { warn: jest.fn(), error: jest.fn(), info: jest.fn() } }));

import { AuthContext } from '../../src/providers/authContext';
import { useBillingLimits } from '../../src/hooks/useBillingLimits';

const PRO = { max_mandates: 10, max_watchlist_items: null, max_daily_deal_alerts: null, advanced_analytics: true };
const as = (id: string) => {
  const SignedIn = ({ children }: { children: React.ReactNode }) => (
    <AuthContext.Provider value={{ user: { id } } as never}>{children}</AuthContext.Provider>
  );
  return SignedIn;
};

it('a later mount starts on the plan already confirmed for this member', async () => {
  mockGetBillingStatus.mockResolvedValue({ plan: 'pro', limits: PRO, status: 'active' });
  const first = renderHook(() => useBillingLimits(), { wrapper: as('u1') });
  await waitFor(() => expect(first.result.current.plan).toBe('pro'));

  mockGetBillingStatus.mockReturnValue(new Promise(() => {})); // still in flight
  const second = renderHook(() => useBillingLimits(), { wrapper: as('u1') });
  expect(second.result.current.plan).toBe('pro');
  expect(second.result.current.limits.advanced_analytics).toBe(true);
});

it('another account does not inherit it', () => {
  mockGetBillingStatus.mockReturnValue(new Promise(() => {}));
  const other = renderHook(() => useBillingLimits(), { wrapper: as('u2') });
  expect(other.result.current.plan).toBe('free');
});
