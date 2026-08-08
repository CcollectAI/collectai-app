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

    // The hook does NOT trust a single offline reading: it re-checks ~1.2s later
    // and only commits offline if still offline (online commits immediately).
    // That debounce exists because iOS reports offline transiently during cold
    // start, which flashed the orange "You're offline" banner at login for new
    // users (2026-06-11).
    //
    // waitFor's default timeout is 1000ms — SHORTER than the debounce — so this
    // test timed out mid-recheck and read as "the hook says online". It was
    // failing on correct code because it did not model deliberate behaviour.
    await waitFor(
      () => {
        expect(result.current.isOnline).toBe(false);
      },
      { timeout: 4000, interval: 100 },
    );
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
    // Call 1 (initial): online. Every call after: offline.
    //
    // This used exactly TWO mockResolvedValueOnce values, which is one short:
    // committing offline takes a THIRD call, because the hook re-checks ~1.2s
    // later before trusting a single offline reading. That third call returned
    // undefined, computeOnline threw, and the catch committed `true`
    // optimistically — so the test saw "online" and failed on correct code.
    //
    // mockResolvedValue (not Once) for the offline state, so the recheck gets a
    // real value however many times it runs.
    mockGetNetworkStateAsync
      .mockResolvedValueOnce({ isConnected: true, isInternetReachable: true })
      .mockResolvedValue({ isConnected: false, isInternetReachable: false });

    const { result } = renderHook(() => useNetworkStatus());

    // Wait for the initial check
    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });

    // Advance past the 10s poll AND the 1.2s offline-confirmation recheck.
    await act(async () => {
      jest.advanceTimersByTime(10_000);
    });
    await act(async () => {
      jest.advanceTimersByTime(1_500);
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
    });
  });
});
