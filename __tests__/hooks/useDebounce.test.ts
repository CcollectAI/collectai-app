import { renderHook, act } from '@testing-library/react-native';
import { useDebounce } from '../../src/hooks/useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('hello', 300));
    expect(result.current).toBe('hello');
  });

  it('does not update the debounced value before the delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 500 } },
    );

    rerender({ value: 'b', delay: 500 });

    // Advance less than the delay
    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(result.current).toBe('a');
  });

  it('updates to the final value after the delay elapses', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 300 } },
    );

    rerender({ value: 'b', delay: 300 });

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(result.current).toBe('b');
  });

  it('only emits the last value after rapid-fire changes', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 300 } },
    );

    // Rapid fire changes — each resets the timer
    rerender({ value: 'b', delay: 300 });
    act(() => { jest.advanceTimersByTime(100); });

    rerender({ value: 'c', delay: 300 });
    act(() => { jest.advanceTimersByTime(100); });

    rerender({ value: 'd', delay: 300 });
    act(() => { jest.advanceTimersByTime(100); });

    // At this point 300ms have NOT elapsed since the last change ('d')
    expect(result.current).toBe('a');

    // Now let the final timer fire
    act(() => { jest.advanceTimersByTime(300); });
    expect(result.current).toBe('d');
  });

  it('respects a custom delay parameter', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'first', delay: 1000 } },
    );

    rerender({ value: 'second', delay: 1000 });

    act(() => { jest.advanceTimersByTime(500); });
    expect(result.current).toBe('first');

    act(() => { jest.advanceTimersByTime(500); });
    expect(result.current).toBe('second');
  });

  it('cleans up the timer on unmount', () => {
    const { result, rerender, unmount } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'init', delay: 300 } },
    );

    rerender({ value: 'updated', delay: 300 });

    // Unmount before timer fires
    unmount();

    // Advancing timers should not cause errors
    act(() => { jest.advanceTimersByTime(500); });

    // The last returned value was still the initial
    expect(result.current).toBe('init');
  });

  it('works with non-string types', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 42, delay: 200 } },
    );

    rerender({ value: 99, delay: 200 });

    act(() => { jest.advanceTimersByTime(200); });
    expect(result.current).toBe(99);
  });
});
