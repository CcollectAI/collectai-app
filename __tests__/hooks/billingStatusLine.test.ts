/**
 * The subscription screen has to say when Pro ends.
 *
 * 2026-09-18, class T ("the server sends it and the app never reads it"). Three
 * pieces of one feature existed and never met:
 *
 *   * `GET /billing/status` has always returned `status`, `current_period_end`
 *     and `cancel_at_period_end`;
 *   * `subscription.past_due` and `subscription.downgrade_pending` were written
 *     and translated into all seven locales;
 *   * `useBillingLimits` kept `plan` and `limits` and dropped the other three,
 *     and nothing rendered either string.
 *
 * So a member who had cancelled saw no end date anywhere in the app.
 *
 * These tests cover the hook's half — that the fields survive the fetch — and
 * `billingStatusLine()`, the function the SCREEN calls, which is where the edge
 * cases are (a null period on an active plan says nothing rather than "Invalid
 * Date"). It is imported, not copied: the first version of this file duplicated
 * the branching, which is how a screen and its test drift apart while both stay
 * green.
 */
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

jest.mock('../../src/lib/logger', () => ({
  logger: { warn: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

import { useBillingLimits } from '../../src/hooks/useBillingLimits';
import { billingStatusLine, billingLineIsWarning } from '../../src/lib/billingStatusLine';

const LIMITS = {
  max_mandates: 10,
  max_watchlist_items: null,
  max_daily_deal_alerts: null,
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('useBillingLimits keeps what the server sends', () => {
  it('exposes status, periodEnd and cancelAtPeriodEnd', async () => {
    mockGetBillingStatus.mockResolvedValue({
      plan: 'pro',
      status: 'active',
      current_period_end: '2026-10-14T00:00:00Z',
      cancel_at_period_end: false,
      limits: LIMITS,
    });

    const { result } = renderHook(() => useBillingLimits());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.plan).toBe('pro');
    expect(result.current.status).toBe('active');
    expect(result.current.periodEnd).toBe('2026-10-14T00:00:00Z');
    expect(result.current.cancelAtPeriodEnd).toBe(false);
  });

  it('a cancelling subscription arrives as cancelAtPeriodEnd true', async () => {
    mockGetBillingStatus.mockResolvedValue({
      plan: 'pro',
      status: 'active',
      current_period_end: '2026-10-14T00:00:00Z',
      cancel_at_period_end: true,
      limits: LIMITS,
    });

    const { result } = renderHook(() => useBillingLimits());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.cancelAtPeriodEnd).toBe(true);
  });

  it('a failed fetch leaves them NULL — unknown, never "nothing to say"', async () => {
    mockGetBillingStatus.mockRejectedValue(new Error('503'));

    const { result } = renderHook(() => useBillingLimits());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.status).toBeNull();
    expect(result.current.periodEnd).toBeNull();
    expect(result.current.cancelAtPeriodEnd).toBeNull();
  });
});

/**
 * The SAME function the screen calls — not a copy of its decision table. The
 * first version of this file copied the branching, which is how a screen and
 * its test drift apart while both stay green.
 */
function statusLineFor(opts: {
  status: string | null;
  periodEndLabel: string | null;
  cancelAtPeriodEnd: boolean | null;
}): string | null {
  const line = billingStatusLine(opts);
  if (!line) return null;
  return line.date ? `${line.key.replace('subscription.', '')}:${line.date}` : line.key.replace('subscription.', '');
}

describe('what the member is told', () => {
  it('an active plan says when it renews', () => {
    expect(statusLineFor({ status: 'active', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: false }))
      .toBe('renews_on:Oct 14, 2026');
  });

  it('a cancelled plan says how long access lasts, not that it renews', () => {
    const line = statusLineFor({ status: 'active', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: true });
    expect(line).toBe('access_until:Oct 14, 2026');
    expect(line).not.toContain('renews');
  });

  it('a payment problem outranks both — it can END the subscription', () => {
    expect(statusLineFor({ status: 'past_due', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: false }))
      .toBe('past_due');
    expect(statusLineFor({ status: 'unpaid', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: true }))
      .toBe('past_due');
  });

  it('cancelling with no date falls back to the dateless sentence', () => {
    // `current_period_end` is nullable on the server; "Invalid Date" is not an
    // acceptable thing to show a paying member.
    expect(statusLineFor({ status: 'active', periodEndLabel: null, cancelAtPeriodEnd: true }))
      .toBe('downgrade_pending');
  });

  it('an active plan with no date says NOTHING rather than an empty line', () => {
    expect(statusLineFor({ status: 'active', periodEndLabel: null, cancelAtPeriodEnd: false }))
      .toBeNull();
  });

  it('an unknown status (failed fetch) says nothing', () => {
    expect(statusLineFor({ status: null, periodEndLabel: null, cancelAtPeriodEnd: null }))
      .toBeNull();
  });
});

describe('which lines ask the member to do something', () => {
  it('past due, cancelling, and "access until" are warnings; a renewal is not', () => {
    const warn = (o: Parameters<typeof billingStatusLine>[0]) =>
      billingLineIsWarning(billingStatusLine(o));
    expect(warn({ status: 'past_due', periodEndLabel: null, cancelAtPeriodEnd: false })).toBe(true);
    expect(warn({ status: 'active', periodEndLabel: null, cancelAtPeriodEnd: true })).toBe(true);
    expect(warn({ status: 'active', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: true })).toBe(true);
    expect(warn({ status: 'active', periodEndLabel: 'Oct 14, 2026', cancelAtPeriodEnd: false })).toBe(false);
    expect(warn({ status: null, periodEndLabel: null, cancelAtPeriodEnd: null })).toBe(false);
  });
});
