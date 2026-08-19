/**
 * RevenueCat IAP integration for Sparrow Collect.
 *
 * - Configure once at app boot via initPurchases().
 * - Re-identify when auth state changes via identifyUser(userId | null).
 * - Subscribe to entitlement changes via addCustomerInfoUpdateListener.
 *
 * Entitlement contract: a single "pro" entitlement on RevenueCat dashboard,
 * linked to monthly + yearly App Store products. Map other entitlements
 * here if/when we add Premium.
 */

import { Platform } from 'react-native';
import Purchases, {
  LOG_LEVEL,
  type CustomerInfo,
  type PurchasesOfferings,
  type PurchasesPackage,
} from 'react-native-purchases';

import { logger } from '@/lib/logger';

export const PRO_ENTITLEMENT_ID = 'pro';
export const PREMIUM_ENTITLEMENT_ID = 'premium';

export type PlanTier = 'free' | 'pro' | 'premium';

const iosKey = process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY ?? '';
const androidKey = process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY ?? '';

/**
 * Why RevenueCat is or is not usable. `isPurchasesAvailable()` used to be the
 * only answer available and it is a BOOLEAN, so `app/subscription.tsx` logged
 * "reason=no-key — EXPO_PUBLIC_REVENUECAT_IOS_KEY missing from this build" for
 * every false — including the case where the key was present and
 * `Purchases.configure()` THREW. A diagnostic that names the wrong cause is
 * worse than none: it sends you to check EAS env vars that were never the
 * problem. (Found 2026-08-17 while triaging "plans couldn't load" on a build
 * that was never capable of selling anything.)
 *
 *   ready              configure() succeeded; the SDK can be asked for products
 *   no-key             no key for this platform in this build. NORMAL for the
 *                      `development` / dev-client profile, whose eas.json env
 *                      block sets only EXPO_PUBLIC_SUPABASE_MODE — the paywall
 *                      cannot work on a dev build no matter what Apple does
 *   configure-failed   key present, the SDK rejected it or the native module is
 *                      missing. OURS to fix, and nothing to do with Apple
 */
export type PurchasesStatus = 'ready' | 'no-key' | 'configure-failed';

let status: PurchasesStatus = 'no-key';

function getApiKey(): string {
  return Platform.OS === 'ios' ? iosKey : androidKey;
}

export function purchasesStatus(): PurchasesStatus {
  return status;
}

export function isPurchasesAvailable(): boolean {
  return status === 'ready';
}

export function initPurchases(): void {
  if (status === 'ready') return;
  const apiKey = getApiKey();
  if (!apiKey) {
    status = 'no-key';
    // logger.warn is stripped in release builds, so this uses .error — a
    // missing key is exactly the thing you need visible on a store build.
    // app/subscription.tsx reads purchasesStatus() and renders its
    // "unavailable" state rather than dead Subscribe buttons, so this is a
    // silent no-revenue failure unless something says so out loud.
    logger.error(
      `[purchases] EXPO_PUBLIC_REVENUECAT_${Platform.OS === 'ios' ? 'IOS' : 'ANDROID'}_KEY ` +
        'not set — IAP disabled, the paywall cannot sell. Free tier still works. ' +
        'Checked by scripts/preflight_android.mjs.',
    );
    return;
  }
  try {
    Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.WARN);
    Purchases.configure({ apiKey });
    status = 'ready';
  } catch (e) {
    status = 'configure-failed';
    logger.error('[purchases] configure failed — a key IS present, so this is ours, not Apple:', e);
  }
}

export async function identifyUser(userId: string | null): Promise<void> {
  if (status !== 'ready') return;
  try {
    if (userId) {
      await Purchases.logIn(userId);
    } else {
      await Purchases.logOut();
    }
  } catch (e) {
    logger.error('[purchases] identifyUser failed:', e);
  }
}

/**
 * Stamp the creator code as a RevenueCat subscriber attribute so it rides along
 * on every webhook event for this user.
 *
 * Kept separate from identifyUser because the code lives on the profile, which
 * loads *after* the session — calling it from identifyUser would almost always
 * pass undefined. AuthProvider calls this once the profile resolves.
 */
export async function setReferralAttribute(referralCode: string | null | undefined): Promise<void> {
  if (status !== 'ready' || !referralCode) return;
  try {
    await Purchases.setAttributes({ affiliate_code: referralCode });
  } catch (e) {
    logger.error('[purchases] setReferralAttribute failed:', e);
  }
}

export function planFromCustomerInfo(info: CustomerInfo | null | undefined): PlanTier {
  if (!info) return 'free';
  const active = info.entitlements.active;
  if (active[PREMIUM_ENTITLEMENT_ID]) return 'premium';
  if (active[PRO_ENTITLEMENT_ID]) return 'pro';
  return 'free';
}

export async function getCustomerInfo(): Promise<CustomerInfo | null> {
  if (status !== 'ready') return null;
  try {
    return await Purchases.getCustomerInfo();
  } catch (e) {
    logger.error('[purchases] getCustomerInfo failed:', e);
    return null;
  }
}

export async function getOfferings(): Promise<PurchasesOfferings | null> {
  if (status !== 'ready') return null;
  try {
    return await Purchases.getOfferings();
  } catch (e) {
    logger.error('[purchases] getOfferings failed:', e);
    return null;
  }
}

export type PurchaseResult =
  | { ok: true; customerInfo: CustomerInfo }
  | { ok: false; cancelled: true }
  | { ok: false; cancelled: false; message: string };

export async function purchasePackage(pkg: PurchasesPackage): Promise<PurchaseResult> {
  if (status !== 'ready') {
    return { ok: false, cancelled: false, message: 'Purchases not configured' };
  }
  try {
    const { customerInfo } = await Purchases.purchasePackage(pkg);
    return { ok: true, customerInfo };
  } catch (e) {
    logger.error('[silent-catch] purchases.ts:130:', e);
    const err = e as { userCancelled?: boolean; message?: string };
    if (err.userCancelled) return { ok: false, cancelled: true };
    return {
      ok: false,
      cancelled: false,
      message: err.message ?? 'Purchase failed',
    };
  }
}

export async function restorePurchases(): Promise<CustomerInfo | null> {
  if (status !== 'ready') return null;
  try {
    return await Purchases.restorePurchases();
  } catch (e) {
    logger.error('[purchases] restorePurchases failed:', e);
    return null;
  }
}

export type CustomerInfoListener = (info: CustomerInfo) => void;

export function addCustomerInfoUpdateListener(listener: CustomerInfoListener): () => void {
  if (status !== 'ready') {
    return () => {};
  }
  Purchases.addCustomerInfoUpdateListener(listener);
  return () => Purchases.removeCustomerInfoUpdateListener(listener);
}
