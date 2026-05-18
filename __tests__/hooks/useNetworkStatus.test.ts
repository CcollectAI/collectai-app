/**
 * useNetworkStatus hook tests.
 *
 * Validates that the hook:
 * - Defaults to online (optimistic)
 * - Reflects the value returned by expo-network
 * - Falls back to online on network check failure
 */
import { renderHook, act, waitFor } from '@testing-library/react-native';
import { useNetworkStatus } from '../../src/hooks/useNetworkStatus';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetNetworkStateAsync = jest.fn();

jest.mock('expo-network', () => ({
  getNetworkStateAsync: (...args: any[]) => mockGetNetworkStateAsync(...args),
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.useFakeTimers();
  mockGetNetworkStateAsync.mockReset();
});

afterEach(() => {
  jest.useRealTimers();
});

describe('useNetworkStatus', () => {
  it('defaults to online (optimistic)', () => {
    // Never resolve the promise so the hook stays in its initial state
    mockGetNetworkStateAsync.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);
  });

  it('reports online when network is reachable', async () => {
    mockGetNetworkStateAsync.mockResolvedValue({
      isConnected: true,
      isInternetReachable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });
  });

  it('reports offline when isConnected is false', async () => {
    // We now consult isConnected ONLY (isInternetReachable returns false
    // transiently on iOS mid-probe and was producing TestFlight #9 false-
    // positives). See src/hooks/useNetworkStatus.ts.
    mockGetNetworkStateAsync.mockResolvedValue({
      isConnected: false,
      isInternetReachable: false,
    });

    const { result } = renderHook(() => useNetworkStatus());

    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
    });
  });

  it('reports online when isInternetReachable is transiently false but isConnected is true', async () => {
    // iOS transient — we intentionally do NOT trust isInternetReachable.
    mockGetNetworkStateAsync.mockResolvedValue({
      isConnected: true,
      isInternetReachable: false,
    });

    const { result } = renderHook(() => useNetworkStatus());

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });
  });

  it('falls back to online when the network check throws', async () => {
    mockGetNetworkStateAsync.mockRejectedValue(new Error('Network API unavailable'));

    const { result } = renderHook(() => useNetworkStatus());

    await waitFor(() => {
      // Should remain true (optimistic fallback)
      expect(result.current.isOnline).toBe(true);
    });
  });

  it('polls network status on interval', async () => {
    // First call: online.  Second call (poll): offline.
    mockGetNetworkStateAsync
      .mockResolvedValueOnce({ isConnected: true, isInternetReachable: true })
      .mockResolvedValueOnce({ isConnected: false, isInternetReachable: false });

    const { result } = renderHook(() => useNetworkStatus());

    // Wait for the initial check
    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });

    // Advance past the 10-second polling interval
    await act(async () => {
      jest.advanceTimersByTime(10_000);
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
    });
  });
});
