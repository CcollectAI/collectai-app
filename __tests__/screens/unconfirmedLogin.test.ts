/**
 * A signed-up, never-confirmed account signing in (2026-09-24). Supabase
 * answers 400 `email_not_confirmed`; the app showed that as a toast and
 * nothing else, and verify-email — the only screen with Resend — was reachable
 * only straight after signUp. Login now routes there with `from=login`.
 */
import { isUnconfirmedEmailError } from '../../app/(auth)/login';
import { initialResendCooldown, RESEND_COOLDOWN_S } from '../../app/(auth)/verify-email';

describe('unconfirmed account at login', () => {
  it('recognises Supabase\'s email_not_confirmed error (shape measured on prod)', () => {
    expect(isUnconfirmedEmailError({ name: 'AuthApiError', status: 400, code: 'email_not_confirmed', message: 'Email not confirmed' })).toBe(true);
  });

  it('leaves wrong passwords and other failures to the toast', () => {
    expect(isUnconfirmedEmailError({ status: 400, code: 'invalid_credentials', message: 'Invalid login credentials' })).toBe(false);
    expect(isUnconfirmedEmailError(new Error('Network request failed'))).toBe(false);
    expect(isUnconfirmedEmailError(null)).toBe(false);
  });

  it('offers Resend at once when arriving from login, after the server cooldown when arriving from signup', () => {
    expect(initialResendCooldown('login')).toBe(0);
    expect(initialResendCooldown(undefined)).toBe(RESEND_COOLDOWN_S);
  });
});
