/**
 * useSlowLoad — pins WHEN the app speaks during a wait.
 *
 * The failure this guards against is not a crash, it is a message that appears
 * on a fast load (noise, and it makes a snappy app look slow) or never appears
 * on a slow one (the silence we added it to fix). Both are invisible without
 * fake timers, so both are asserted here.
 */
import { jest } from '@jest/globals';
import { renderHook, act } from '@testing-library/react-native';
import { useSlowLoad, SLOW_AFTER_MS, VERY_SLOW_AFTER_MS } from '../../src/hooks/useSlowLoad';

describe('useSlowLoad', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('says nothing before 3s — a fast load must stay silent', () => {
    const { result } = renderHook(() => useSlowLoad(true));
    expect(result.current.isSlow).toBe(false);

    act(() => {
      jest.advanceTimersByTime(SLOW_AFTER_MS - 1);
    });
    expect(result.current.isSlow).toBe(false);
  });

  it('speaks up once the wait passes 3s', () => {
    const { result } = renderHook(() => useSlowLoad(true));

    act(() => {
      jest.advanceTimersByTime(SLOW_AFTER_MS);
    });
    expect(result.current.isSlow).toBe(true);
    // Not escalated yet — one message at a time.
    expect(result.current.isVerySlow).toBe(false);
  });

  it('escalates the wording at 10s so a long wait does not look frozen', () => {
    const { result } = renderHook(() => useSlowLoad(true));

    act(() => {
      jest.advanceTimersByTime(VERY_SLOW_AFTER_MS);
    });
    expect(result.current.isSlow).toBe(true);
    expect(result.current.isVerySlow).toBe(true);
  });

  it('never fires for a load that finishes quickly', () => {
    const { result, rerender } = renderHook(({ loading }) => useSlowLoad(loading), {
      initialProps: { loading: true },
    });

    // Resolved at 1s, well inside the threshold.
    act(() => {
      jest.advanceTimersByTime(1_000);
    });
    rerender({ loading: false });

    // Past the threshold in wall-clock terms, but the wait is over.
    act(() => {
      jest.advanceTimersByTime(SLOW_AFTER_MS * 2);
    });
    expect(result.current.isSlow).toBe(false);
  });

  it('resets between waits, so a slow load does not poison the next fast one', () => {
    const { result, rerender } = renderHook(({ loading }) => useSlowLoad(loading), {
      initialProps: { loading: true },
    });

    act(() => {
      jest.advanceTimersByTime(VERY_SLOW_AFTER_MS);
    });
    expect(result.current.isVerySlow).toBe(true);

    rerender({ loading: false });
    expect(result.current.isSlow).toBe(false);
    expect(result.current.isVerySlow).toBe(false);

    // A second, fast wait starts from silence.
    rerender({ loading: true });
    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(result.current.isSlow).toBe(false);
  });
});
