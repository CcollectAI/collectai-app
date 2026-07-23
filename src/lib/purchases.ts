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

let configured = false;

function getApiKey(): string {
  return Platform.OS === 'ios' ? iosKey : androidKey;
}

export function isPurchasesAvailable(): boolean {
  return configured;
}

export function initPurchases(): void {
  if (configured) return;
  const apiKey = getApiKey();
  if (!apiKey) {
    logger.warn(
      '[purchases] EXPO_PUBLIC_REVENUECAT_*_KEY not set — IAP disabled. ' +
        'Free tier still works; users will see "Subscribe" buttons that fail until configured.',
    );
    return;
  }
  try {
    Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.WARN);
    Purchases.configure({ apiKey });
    configured = true;
  } catch (e) {
    logger.warn('[purchases] configure failed:', e);
  }
}

export async function identifyUser(userId: string | null): Promise<void> {
  if (!configured) return;
  try {
    if (userId) {
      await Purchases.logIn(userId);
    } else {
      await Purchases.logOut();
    }
  } catch (e) {
    logger.warn('[purchases] identifyUser failed:', e);
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
  if (!configured || !referralCode) return;
  try {
    await Purchases.setAttributes({ affiliate_code: referralCode });
  } catch (e) {
    logger.warn('[purchases] setReferralAttribute failed:', e);
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
  if (!configured) return null;
  try {
    return await Purchases.getCustomerInfo();
  } catch (e) {
    logger.warn('[purchases] getCustomerInfo failed:', e);
    return null;
  }
}

export async function getOfferings(): Promise<PurchasesOfferings | null> {
  if (!configured) return null;
  try {
    return await Purchases.getOfferings();
  } catch (e) {
    logger.warn('[purchases] getOfferings failed:', e);
    return null;
  }
}

export type PurchaseResult =
  | { ok: true; customerInfo: CustomerInfo }
  | { ok: false; cancelled: true }
  | { ok: false; cancelled: false; message: string };

export async function purchasePackage(pkg: PurchasesPackage): Promise<PurchaseResult> {
  if (!configured) {
    return { ok: false, cancelled: false, message: 'Purchases not configured' };
  }
  try {
    const { customerInfo } = await Purchases.purchasePackage(pkg);
    return { ok: true, customerInfo };
  } catch (e) {
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
  if (!configured) return null;
  try {
    return await Purchases.restorePurchases();
  } catch (e) {
    logger.warn('[purchases] restorePurchases failed:', e);
    return null;
  }
}

export type CustomerInfoListener = (info: CustomerInfo) => void;

export function addCustomerInfoUpdateListener(listener: CustomerInfoListener): () => void {
  if (!configured) {
    return () => {};
  }
  Purchases.addCustomerInfoUpdateListener(listener);
  return () => Purchases.removeCustomerInfoUpdateListener(listener);
}
