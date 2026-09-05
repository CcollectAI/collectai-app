/**
 * The resend button used to do nothing at all when rate-limited.
 *
 * `handleResend` threw into a bare `catch {}`, so a 429 left `resent` false
 * and `cooldown` 0: no confirmation, no error, no countdown. The user taps
 * "Resend email" on the one screen whose whole job is "your email is coming",
 * and gets silence — so they tap again.
 *
 * The strings below are REAL responses measured against production Supabase on
 * 2026-09-05, not invented:
 *
 *   resend at +0s   -> 429 "For security purposes, you can only request this after 58 seconds."
 *   resend at +20s  -> 429 "... after 38 seconds."
 *   resend at +45s  -> 429 "... after 13 seconds."
 *   resend at +70s  -> 200, and a second email really arrived.
 */
import { rateLimitSeconds, RESEND_COOLDOWN_S } from '../../app/(auth)/verify-email';

describe('rateLimitSeconds', () => {
  it('reads the server\'s own remaining seconds', () => {
    expect(
      rateLimitSeconds({
        status: 429,
        code: 'over_email_send_rate_limit',
        message: 'For security purposes, you can only request this after 58 seconds.',
      }),
    ).toBe(58);
  });

  it('tracks the countdown as it shrinks', () => {
    const msg = (n: number) =>
      `For security purposes, you can only request this after ${n} seconds.`;
    expect(rateLimitSeconds({ status: 429, message: msg(38) })).toBe(38);
    expect(rateLimitSeconds({ status: 429, message: msg(13) })).toBe(13);
  });

  it('recognises the rate limit by code alone, without a status', () => {
    expect(rateLimitSeconds({ code: 'over_email_send_rate_limit' })).toBe(RESEND_COOLDOWN_S);
  });

  it('falls back to the full cooldown if the wording changes', () => {
    expect(rateLimitSeconds({ status: 429, message: 'slow down please' })).toBe(
      RESEND_COOLDOWN_S,
    );
  });

  it('returns null for anything else, so other errors stay silent', () => {
    // The account-enumeration defence: a non-rate-limit failure must NOT
    // surface, because it could reveal whether the address exists.
    expect(rateLimitSeconds({ status: 400, message: 'User not found' })).toBeNull();
    expect(rateLimitSeconds(null)).toBeNull();
    expect(rateLimitSeconds(undefined)).toBeNull();
    expect(rateLimitSeconds(new Error('network down'))).toBeNull();
  });

  it('never returns a non-positive wait', () => {
    const n = rateLimitSeconds({ status: 429, message: '... after 0 seconds.' });
    expect(n).toBe(RESEND_COOLDOWN_S);
  });
});
