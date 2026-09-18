/**
 * What the subscription screen tells a paying member about their period.
 *
 * Extracted from `app/subscription.tsx` on 2026-09-18 so the branching has ONE
 * implementation. The first version of its test copied the decision table into
 * the test file, which is the shape that lets a screen and its test drift apart
 * while both stay green.
 *
 * Why this exists at all (class T, docs/CLASS_SWEEPS.md): `GET /billing/status`
 * has always returned `status`, `current_period_end` and `cancel_at_period_end`;
 * `useBillingLimits` kept `plan` and `limits` and dropped the other three, and
 * `subscription.past_due` / `subscription.downgrade_pending` — copy already
 * translated into seven locales — was rendered by nothing. A member who had
 * cancelled saw no end date anywhere in the app.
 */

export type BillingLineKey =
  | 'subscription.past_due'
  | 'subscription.downgrade_pending'
  | 'subscription.access_until'
  | 'subscription.renews_on';

export type BillingLine = { key: BillingLineKey; date?: string } | null;

/**
 * `null` means "say nothing", which is a real answer and not a failure:
 * an active plan whose `current_period_end` is null has a status and nothing to
 * report, and rendering the sentence-shaped empty string there would put a
 * blank line under the plan cards.
 *
 * Order is by what can cost the member their subscription: a payment problem
 * first (it ENDS the plan), then a pending cancellation, then the ordinary
 * renewal.
 */
export function billingStatusLine(opts: {
  status: string | null;
  /** Already formatted for display — the caller owns the locale. */
  periodEndLabel: string | null;
  cancelAtPeriodEnd: boolean | null;
}): BillingLine {
  const { status, periodEndLabel, cancelAtPeriodEnd } = opts;

  if (status === 'past_due' || status === 'unpaid') {
    return { key: 'subscription.past_due' };
  }
  if (cancelAtPeriodEnd) {
    // `current_period_end` is nullable on the server, and "Invalid Date" is not
    // an acceptable thing to show someone who is paying.
    return periodEndLabel
      ? { key: 'subscription.access_until', date: periodEndLabel }
      : { key: 'subscription.downgrade_pending' };
  }
  return periodEndLabel
    ? { key: 'subscription.renews_on', date: periodEndLabel }
    : null;
}

/** True when the line is about something the member may need to act on. */
export function billingLineIsWarning(line: BillingLine): boolean {
  return (
    line?.key === 'subscription.past_due' ||
    line?.key === 'subscription.downgrade_pending' ||
    line?.key === 'subscription.access_until'
  );
}
