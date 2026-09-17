/**
 * A guessed fee must not be printed like a known one.
 *
 * 2026-09-17 (class sweep D): the marketplace fee is computed in two places.
 * `CreateListingModal` shows NO preview until the server's schedule arrives;
 * `useListForSale.calculateFee` falls back to
 * `MARKETPLACE_OPTIONS.defaultFeePct` — a client guess — and the breakdown rows
 * printed "-EUR 12,90 / EUR 87,10" with nothing to say the rate was assumed.
 * eBay's real fee is not one flat number, so that figure can be wrong by euros
 * on a real listing. The picker chip already said "~12.9% fee"; the numbers
 * underneath did not.
 */
const mockGetSchedules = jest.fn();
jest.mock('@/data', () => ({
  dataProvider: {
    getMarketplaceFeeSchedules: () => mockGetSchedules(),
    createMarketplaceListing: jest.fn(),
  },
}));
jest.mock('@/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { renderHook, act, waitFor } from '@testing-library/react-native';
import { useListForSale } from '../../src/hooks/useListForSale';

const opts = { itemId: 'i1', itemName: 'Charizard', currency: 'EUR' as const };

describe('useListForSale.calculateFee', () => {
  beforeEach(() => jest.clearAllMocks());

  it('marks the breakdown as ESTIMATED when the server schedule is missing', async () => {
    mockGetSchedules.mockResolvedValue([]);
    const { result } = renderHook(() => useListForSale(opts));
    act(() => { result.current.open(); });
    await waitFor(() => expect(mockGetSchedules).toHaveBeenCalled());

    const fee = result.current.calculateFee('ebay', '100');
    expect(fee).not.toBeNull();
    expect(fee!.estimated).toBe(true);
    // 12.9% is the client's guess for eBay
    expect(fee!.totalFees).toBeCloseTo(12.9, 2);
  });

  it('is NOT estimated once the server schedule is used, and follows its numbers', async () => {
    mockGetSchedules.mockResolvedValue([
      { marketplaceId: 'ebay', baseFeePct: 10, paymentProcessingPct: 2, fixedFee: 0.3 },
    ]);
    const { result } = renderHook(() => useListForSale(opts));
    act(() => { result.current.open(); });
    await waitFor(() => expect(mockGetSchedules).toHaveBeenCalled());
    await waitFor(() => {
      expect(result.current.calculateFee('ebay', '100')?.estimated).toBe(false);
    });

    const fee = result.current.calculateFee('ebay', '100')!;
    expect(fee.totalFees).toBeCloseTo(12.3, 2);   // 10 + 2 + 0.30, not the 12.9 guess
    expect(fee.netProceeds).toBeCloseTo(87.7, 2);
  });

  it('an unreadable price has no breakdown at all — never a zero fee', () => {
    mockGetSchedules.mockResolvedValue([]);
    const { result } = renderHook(() => useListForSale(opts));
    expect(result.current.calculateFee('ebay', '')).toBeNull();
    expect(result.current.calculateFee('ebay', 'abc')).toBeNull();
    expect(result.current.calculateFee('ebay', '0')).toBeNull();
  });
});
