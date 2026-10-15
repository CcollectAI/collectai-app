/**
 * "Billing not available on this device" is not a retryable failure
 * (2026-10-15, emulator with no Google account: RevenueCat
 * PURCHASE_NOT_ALLOWED_ERROR). The subscription screen tells the member what to
 * change instead of "check your connection".
 */
jest.mock('react-native-purchases', () => ({ __esModule: true, default: {}, LOG_LEVEL: {} }));
jest.mock('@/lib/logger', () => ({ logger: { error: jest.fn(), warn: jest.fn(), info: jest.fn() } }));

import { isBillingUnavailableError } from '@/lib/purchases';

describe('isBillingUnavailableError', () => {
  it('recognises the RevenueCat code and readable code', () => {
    expect(isBillingUnavailableError(Object.assign(new Error('The device or user is not allowed to make the purchase.'), { code: '3' }))).toBe(true);
    expect(isBillingUnavailableError({ code: 3 })).toBe(true);
    expect(isBillingUnavailableError({ userInfo: { readableErrorCode: 'PurchaseNotAllowedError' } })).toBe(true);
  });
  it('leaves network and other store errors to the retry path', () => {
    expect(isBillingUnavailableError(Object.assign(new Error('Network'), { code: '10' }))).toBe(false);
    expect(isBillingUnavailableError(new Error('Could not load offerings'))).toBe(false);
    expect(isBillingUnavailableError(null)).toBe(false);
  });
});
