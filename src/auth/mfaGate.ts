/**
 * Does this session still owe its second factor?
 *
 * 2026-09-24, walked on Android: 2FA could be enrolled and the settings screen
 * said "Your account is protected with two-factor authentication", but nothing
 * ever asked for the code. `signInWithPassword` yields an aal1 session, and the
 * app went straight in. The root gate (app/_layout.tsx) now sends any session
 * whose next level is aal2 to /(auth)/mfa-challenge first — on sign-in AND on a
 * cold start, so killing the app mid-login cannot skip it.
 *
 * getAuthenticatorAssuranceLevel() reads the session locally (the JWT's `aal`
 * and the user's factors); it makes no request.
 */
import { supabase } from '@/lib/supabase';
import { logger } from '@/lib/logger';

export type AalLevels = { currentLevel: string | null; nextLevel: string | null };

/** Pure rule, tested: a factor is due when the session could be aal2 but is not. */
export function owesSecondFactor(l: AalLevels | null | undefined): boolean {
  return !!l && l.nextLevel === 'aal2' && l.currentLevel !== 'aal2';
}

export async function needsMfaChallenge(): Promise<boolean> {
  try {
    const { data, error } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    if (error) throw error;
    return owesSecondFactor(data);
  } catch (e) {
    // Fail CLOSED for a member who has 2FA: if the level cannot be read, we
    // cannot tell, and letting them in is the failure 2FA exists to prevent.
    // A member without 2FA has no factors, so this path only costs them a
    // retry on the challenge screen, which offers sign-out.
    logger.error('[mfaGate] could not read the assurance level:', e);
    return true;
  }
}
