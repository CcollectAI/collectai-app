/**
 * Creator referral code capture.
 *
 * The only ways a code can reach the app:
 *   1. A universal link — https://sparrowcollect.com/r/LUNA10 (or any link with
 *      ?ref=LUNA10). Works when the app is already installed.
 *   2. The user typing it on the register screen, prefilled from (1) when
 *      available.
 *
 * There is deliberately no install-attribution SDK (Branch/AppsFlyer), so a
 * code CANNOT survive an App Store round-trip on a fresh install. The landing
 * page therefore shows the code and asks the user to enter it. Anything that
 * claims otherwise would be attributing installs it cannot actually observe.
 *
 * Stored rather than applied immediately because the link usually arrives
 * before the user has an account — it has to survive until registration.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { logger } from '@/lib/logger';

const PENDING_KEY = 'sparrow.pendingReferralCode';

/** Codes are compared upper-case everywhere: signup, trigger, admin write route. */
export function normaliseCode(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const v = raw.trim().toUpperCase();
  // Guard the storage layer against junk arriving from a URL.
  if (!v || v.length > 32 || !/^[A-Z0-9_-]+$/.test(v)) return null;
  return v;
}

/**
 * Pull a referral code out of an inbound URL.
 *
 * Handles both shapes we publish:
 *   https://sparrowcollect.com/r/LUNA10
 *   sparrow://...?ref=LUNA10   (also ?referral_code= / ?utm_content=)
 *
 * Written against the raw string rather than URL(): React Native's URL polyfill
 * does not parse custom schemes like sparrow:// reliably.
 */
export function extractReferralCode(url: string | null | undefined): string | null {
  if (!url) return null;

  // Query parameter form. Deliberately scans the whole string so it works for
  // custom schemes, and stops at the fragment so #access_token is never read.
  const qIdx = url.indexOf('?');
  if (qIdx !== -1) {
    const hashIdx = url.indexOf('#');
    const query = hashIdx > qIdx ? url.slice(qIdx + 1, hashIdx) : url.slice(qIdx + 1);
    for (const kv of query.split('&')) {
      const eq = kv.indexOf('=');
      if (eq === -1) continue;
      const key = kv.slice(0, eq).toLowerCase();
      if (key === 'ref' || key === 'referral_code' || key === 'utm_content') {
        const code = normaliseCode(decodeURIComponent(kv.slice(eq + 1)));
        if (code) return code;
      }
    }
  }

  // Path form: /r/<CODE>, with any trailing path/query/fragment stripped.
  const m = url.match(/\/r\/([^/?#]+)/i);
  if (m) return normaliseCode(decodeURIComponent(m[1]));

  return null;
}

/**
 * Remember a code until the user registers.
 *
 * First write wins: if someone arrives via two creators' links, the one that
 * actually brought them to the app gets the credit rather than whichever they
 * happened to tap last.
 */
export async function storePendingReferralCode(code: string | null): Promise<void> {
  if (!code) return;
  try {
    const existing = await AsyncStorage.getItem(PENDING_KEY);
    if (existing) return;
    await AsyncStorage.setItem(PENDING_KEY, code);
  } catch (e) {
    // Attribution is best-effort and must never break a deep link.
    logger.error('[referral] failed to store pending code', e);
  }
}

/** Read the stored code, for prefilling the register screen. */
export async function getPendingReferralCode(): Promise<string | null> {
  try {
    return normaliseCode(await AsyncStorage.getItem(PENDING_KEY));
  } catch (e) {
    logger.error('[referral] failed to read pending code', e);
    return null;
  }
}

/** Clear after a successful signup, so it cannot attach to a second account. */
export async function clearPendingReferralCode(): Promise<void> {
  try {
    await AsyncStorage.removeItem(PENDING_KEY);
  } catch (e) {
    logger.error('[referral] failed to clear pending code', e);
  }
}

/** Capture from an inbound URL. Safe to call on every link the app receives. */
export async function captureReferralFromUrl(url: string | null | undefined): Promise<string | null> {
  const code = extractReferralCode(url);
  if (code) await storePendingReferralCode(code);
  return code;
}
