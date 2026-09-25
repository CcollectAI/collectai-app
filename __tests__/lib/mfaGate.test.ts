/**
 * 2FA was enrolled and never asked for (2026-09-24): an aal1 session went
 * straight into the app. The root gate now sends a session that owes its
 * second factor to /(auth)/mfa-challenge. This pins the rule it uses.
 */
jest.mock('@/lib/supabase', () => ({ supabase: { auth: { mfa: { getAuthenticatorAssuranceLevel: jest.fn() } } } }));
import { owesSecondFactor, needsMfaChallenge } from '@/auth/mfaGate';
import { supabase } from '@/lib/supabase';

const aal = supabase.auth.mfa.getAuthenticatorAssuranceLevel as jest.Mock;

describe('owesSecondFactor', () => {
  it('password-only session of a member with 2FA owes the code', () => {
    expect(owesSecondFactor({ currentLevel: 'aal1', nextLevel: 'aal2' })).toBe(true);
  });
  it('a member who already gave the code does not', () => {
    expect(owesSecondFactor({ currentLevel: 'aal2', nextLevel: 'aal2' })).toBe(false);
  });
  it('a member without 2FA does not', () => {
    expect(owesSecondFactor({ currentLevel: 'aal1', nextLevel: 'aal1' })).toBe(false);
    expect(owesSecondFactor(null)).toBe(false);
  });
});

describe('needsMfaChallenge', () => {
  it('reads the level from supabase', async () => {
    aal.mockResolvedValueOnce({ data: { currentLevel: 'aal1', nextLevel: 'aal2' }, error: null });
    await expect(needsMfaChallenge()).resolves.toBe(true);
    aal.mockResolvedValueOnce({ data: { currentLevel: 'aal1', nextLevel: 'aal1' }, error: null });
    await expect(needsMfaChallenge()).resolves.toBe(false);
  });
  it('fails closed when the level cannot be read', async () => {
    aal.mockResolvedValueOnce({ data: null, error: new Error('boom') });
    await expect(needsMfaChallenge()).resolves.toBe(true);
  });
});
