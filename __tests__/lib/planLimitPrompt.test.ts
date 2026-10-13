/**
 * A free member at a plan cap gets an offer, not "try again" (2026-09-24).
 * The server's coded 403s were read by one screen; four watch controls turned
 * PLAN_LIMIT_WATCHLIST into a generic failure toast.
 */
import { Alert } from 'react-native';

// The hook module pulls native code; the helper only needs the free cap, whose
// real value check:billing-limits-parity already pins against the server.
jest.mock('@/hooks/useBillingLimits', () => ({ FREE_PLAN_LIMITS: { max_watchlist_items: 25, max_items: 100 } }));
import { offerProOnPlanLimit, planLimitCode } from '@/lib/planLimitPrompt';

const t = ((key: string, opts?: Record<string, unknown>) =>
  opts?.count !== undefined ? `${key}:${opts.count}` : key) as never;

describe('offerProOnPlanLimit', () => {
  beforeEach(() => jest.spyOn(Alert, 'alert').mockImplementation(() => {}));
  afterEach(() => jest.restoreAllMocks());

  it('offers Pro on the watchlist cap, naming the free cap, and the button opens the paywall', () => {
    const open = jest.fn();
    const handled = offerProOnPlanLimit({ name: 'ApiError', status: 403, code: 'PLAN_LIMIT_WATCHLIST' }, t, open);
    expect(handled).toBe(true);
    const [title, body, buttons] = (Alert.alert as jest.Mock).mock.calls[0];
    expect(title).toBe('billing.limit_watchlist_title');
    expect(body).toBe('billing.limit_watchlist_body:25');
    buttons.find((b: { text: string }) => b.text === 'billing.see_pro').onPress();
    expect(open).toHaveBeenCalledTimes(1);
  });

  it('offers Pro on the other plan codes with the generic copy', () => {
    for (const code of ['PLAN_LIMIT_ALERTS', 'PLAN_REQUIRED']) {
      expect(offerProOnPlanLimit({ code }, t, jest.fn())).toBe(true);
    }
    expect((Alert.alert as jest.Mock).mock.calls.map((c) => c[0]))
      .toEqual(['billing.limit_generic_title', 'billing.limit_generic_title']);
  });

  // 2026-10-13: the free-plan item cap is a DB trigger (trg_items_free_cap).
  // Via the API it is code PLAN_LIMIT_ITEMS; via add-manual's direct
  // supabase-js insert it is Postgres P0001 with the marker in the message.
  it('offers Pro on the item cap from the API and from a direct supabase insert', () => {
    const fromApi = { name: 'ApiError', status: 403, code: 'PLAN_LIMIT_ITEMS' };
    const fromSupabase = { code: 'P0001', message: 'PLAN_LIMIT_ITEMS: the free plan holds 100 items' };
    for (const err of [fromApi, fromSupabase]) {
      expect(planLimitCode(err)).toBe('PLAN_LIMIT_ITEMS');
      expect(offerProOnPlanLimit(err, t, jest.fn())).toBe(true);
    }
    const calls = (Alert.alert as jest.Mock).mock.calls;
    expect(calls.map((c) => c[0])).toEqual(['billing.limit_items_title', 'billing.limit_items_title']);
    expect(calls[0][1]).toBe('billing.limit_items_body:100');
  });

  it('does not take an unrelated Postgres P0001 for the item cap', () => {
    expect(planLimitCode({ code: 'P0001', message: 'some other raise' })).toBeNull();
  });

  it('leaves every other failure to the caller', () => {
    for (const err of [new Error('network'), { code: 'UNKNOWN_ERROR' }, null, undefined, { status: 403 }]) {
      expect(offerProOnPlanLimit(err, t, jest.fn())).toBe(false);
      expect(planLimitCode(err)).toBeNull();
    }
    expect(Alert.alert).not.toHaveBeenCalled();
  });
});
