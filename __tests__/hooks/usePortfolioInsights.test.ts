import { renderHook, waitFor } from '@testing-library/react-native';
import { usePortfolioInsights } from '../../src/hooks/usePortfolioInsights';

const mockListItems = jest.fn();
const mockGetPortfolioSummary = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    listItems: (...args: unknown[]) => mockListItems(...args),
    getPortfolioSummary: (...args: unknown[]) => mockGetPortfolioSummary(...args),
  },
}));

jest.mock('../../src/config/featureFlags', () => ({
  featureFlags: { FEATURE_DATA_INSIGHTS_ALERTS: true },
}));

const MOCK_ITEMS = [
  { id: '1', name: 'Card A', category: 'pokemon', price: 100, imageUrl: '', priceBand: { q10: 80, q50: 90, q90: 120 } },
  { id: '2', name: 'Card B', category: 'mtg', price: 50, imageUrl: '', priceBand: { q10: 30, q50: 60, q90: 80 } },
  { id: '3', name: 'Card C', category: 'lorcana', price: 25, imageUrl: '', priceBand: null },
];

// `total` is the authoritative portfolio value from the backend. It is
// deliberately NOT the sum of MOCK_ITEMS (which is 175): `items` is capped at
// limit:50 for the movers calculation, so summing it reported the value of the
// first 50 items as the user's whole portfolio. The gap between 4200 and 175 is
// what makes that regression detectable here.
const MOCK_SUMMARY = { total: 4200, deltaPct: 5.5, itemCount: 3 };

describe('usePortfolioInsights', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts in loading state on mount', () => {
    // Never-resolving promises to keep loading state
    mockListItems.mockReturnValue(new Promise(() => {}));
    mockGetPortfolioSummary.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => usePortfolioInsights());

    // isLoading should be true while fetching
    expect(result.current.isLoading).toBe(true);
    expect(result.current.insights).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('returns insights on successful data fetch', async () => {
    mockListItems.mockResolvedValue(MOCK_ITEMS);
    mockGetPortfolioSummary.mockResolvedValue(MOCK_SUMMARY);

    const { result } = renderHook(() => usePortfolioInsights({ period: '7d' }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeNull();
    expect(result.current.insights).not.toBeNull();
    // The authoritative summary total, NOT sum(MOCK_ITEMS) === 175.
    expect(result.current.insights!.totalValue).toBe(4200);
    expect(result.current.insights!.period).toBe('7d');
    expect(result.current.insights!.percentChange).toBe(5.5);
    // topGainers: Card A (price 100 > q50 90)
    expect(result.current.insights!.topGainers.length).toBeGreaterThanOrEqual(1);
    // topLosers: Card B (price 50 < q50 60)
    expect(result.current.insights!.topLosers.length).toBeGreaterThanOrEqual(1);
  });

  it('returns error state when data provider fails', async () => {
    mockListItems.mockRejectedValue(new Error('Network error'));
    mockGetPortfolioSummary.mockResolvedValue(MOCK_SUMMARY);

    const { result } = renderHook(() => usePortfolioInsights());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error!.message).toBe('Network error');
    expect(result.current.insights).toBeNull();
  });

  it('does not fetch when enabled is false', async () => {
    mockListItems.mockResolvedValue(MOCK_ITEMS);
    mockGetPortfolioSummary.mockResolvedValue(MOCK_SUMMARY);

    const { result } = renderHook(() =>
      usePortfolioInsights({ enabled: false }),
    );

    // Should not start loading since enabled=false
    expect(result.current.isLoading).toBe(false);
    expect(result.current.insights).toBeNull();
    expect(mockListItems).not.toHaveBeenCalled();
  });

  it('wraps non-Error exceptions in an Error object', async () => {
    mockListItems.mockRejectedValue('string error');
    mockGetPortfolioSummary.mockResolvedValue(MOCK_SUMMARY);

    const { result } = renderHook(() => usePortfolioInsights());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error!.message).toBe('Failed to fetch insights');
  });

  it('takes totalValue from the summary, never from the capped items page', async () => {
    // Regression: `items` is fetched with limit:50 for movers. Summing it made
    // InsightsCard render the value of at most 50 items as the whole portfolio,
    // and `item.price || 0` counted every unpriced item as worth 0. Both
    // understate a number shown to the user as their total.
    mockListItems.mockResolvedValue(MOCK_ITEMS);           // sums to 175
    mockGetPortfolioSummary.mockResolvedValue({ total: 98_765, deltaPct: 0, itemCount: 900 });

    const { result } = renderHook(() => usePortfolioInsights({ period: '7d' }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.insights!.totalValue).toBe(98_765);
    expect(result.current.insights!.totalValue).not.toBe(175);
  });

  it('computes watchlistSummary.totalItems from items length', async () => {
    mockListItems.mockResolvedValue(MOCK_ITEMS);
    mockGetPortfolioSummary.mockResolvedValue(MOCK_SUMMARY);

    const { result } = renderHook(() => usePortfolioInsights());

    await waitFor(() => {
      expect(result.current.insights).not.toBeNull();
    });

    expect(result.current.insights!.watchlistSummary.totalItems).toBe(3);
  });
});
