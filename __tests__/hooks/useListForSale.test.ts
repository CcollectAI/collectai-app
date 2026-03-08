import { renderHook, act } from '@testing-library/react-native';
import { useListForSale, MARKETPLACE_OPTIONS } from '../../src/hooks/useListForSale';

const mockCreateMarketplaceListing = jest.fn();
const mockGetMarketplaceFeeSchedules = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    createMarketplaceListing: (...args: unknown[]) => mockCreateMarketplaceListing(...args),
    getMarketplaceFeeSchedules: (...args: unknown[]) => mockGetMarketplaceFeeSchedules(...args),
  },
}));

const DEFAULT_OPTS = {
  itemId: 'item-123',
  itemName: 'Test Card',
  currency: 'EUR' as const,
  suggestedPrice: 50,
};

describe('useListForSale', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMarketplaceFeeSchedules.mockResolvedValue([]);
  });

  it('starts with modal hidden and no marketplaces selected', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    expect(result.current.visible).toBe(false);
    expect(result.current.selectedIds).toEqual([]);
    expect(result.current.submitting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('open() makes modal visible and close() hides it', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    act(() => {
      result.current.open();
    });
    expect(result.current.visible).toBe(true);

    act(() => {
      result.current.close();
    });
    expect(result.current.visible).toBe(false);
  });

  it('toggleMarketplace adds and removes marketplace IDs', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    // Select 'ebay'
    act(() => {
      result.current.toggleMarketplace('ebay');
    });
    expect(result.current.selectedIds).toContain('ebay');

    // Select 'mercari'
    act(() => {
      result.current.toggleMarketplace('mercari');
    });
    expect(result.current.selectedIds).toContain('ebay');
    expect(result.current.selectedIds).toContain('mercari');
    expect(result.current.selectedIds).toHaveLength(2);

    // Deselect 'ebay'
    act(() => {
      result.current.toggleMarketplace('ebay');
    });
    expect(result.current.selectedIds).not.toContain('ebay');
    expect(result.current.selectedIds).toContain('mercari');
    expect(result.current.selectedIds).toHaveLength(1);
  });

  it('calculateFee returns expected fee breakdown using client-side defaults', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    const ebayFee = result.current.calculateFee('ebay', '100');
    expect(ebayFee).not.toBeNull();
    expect(ebayFee!.price).toBe(100);
    // eBay default fee is 12.9%
    expect(ebayFee!.totalFees).toBe(12.9);
    expect(ebayFee!.netProceeds).toBe(87.1);
    expect(ebayFee!.marketplaceId).toBe('ebay');
  });

  it('calculateFee returns null for invalid price input', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    expect(result.current.calculateFee('ebay', '')).toBeNull();
    expect(result.current.calculateFee('ebay', 'abc')).toBeNull();
    expect(result.current.calculateFee('ebay', '0')).toBeNull();
    // Note: '-10' becomes '10' after stripping non-digit chars, so it returns a valid fee
    expect(result.current.calculateFee('ebay', '-10')).not.toBeNull();
  });

  it('canSubmit is false when no marketplaces are selected', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));
    expect(result.current.canSubmit).toBe(false);
  });

  it('canSubmit is true when a marketplace is selected with a valid price', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    act(() => {
      result.current.toggleMarketplace('collectai');
    });

    // suggestedPrice is 50, so the default price is '50'
    expect(result.current.canSubmit).toBe(true);
  });

  it('submit calls createMarketplaceListing for each selected marketplace', async () => {
    mockCreateMarketplaceListing.mockResolvedValue({});
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    act(() => {
      result.current.toggleMarketplace('collectai');
      result.current.toggleMarketplace('ebay');
    });

    let success: boolean | undefined;
    await act(async () => {
      success = await result.current.submit();
    });

    expect(success).toBe(true);
    expect(mockCreateMarketplaceListing).toHaveBeenCalledTimes(2);
    // Modal should be closed after successful submission
    expect(result.current.visible).toBe(false);
  });

  it('submit sets error on API failure', async () => {
    mockCreateMarketplaceListing.mockRejectedValue(new Error('Server error'));
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    act(() => {
      result.current.open();
      result.current.toggleMarketplace('ebay');
    });

    let success: boolean | undefined;
    await act(async () => {
      success = await result.current.submit();
    });

    expect(success).toBe(false);
    expect(result.current.error).toBe('Server error');
    expect(result.current.submitting).toBe(false);
  });

  it('setFormat and setCondition update state', () => {
    const { result } = renderHook(() => useListForSale(DEFAULT_OPTS));

    expect(result.current.format).toBe('fixed_price');
    expect(result.current.condition).toBe('Good');

    act(() => {
      result.current.setFormat('auction');
      result.current.setCondition('Mint');
    });

    expect(result.current.format).toBe('auction');
    expect(result.current.condition).toBe('Mint');
  });
});
