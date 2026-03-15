/**
 * useModal hook tests.
 *
 * Validates that the hook:
 * - Defaults to visible=false
 * - Supports custom initial state
 * - open() sets visible to true
 * - close() sets visible to false
 * - toggle() flips visible state
 */
import { renderHook, act } from '@testing-library/react-native';
import { useModal } from '../../src/hooks/useModal';

describe('useModal', () => {
  it('defaults to visible=false', () => {
    const { result } = renderHook(() => useModal());
    const [visible] = result.current;
    expect(visible).toBe(false);
  });

  it('accepts initial=true', () => {
    const { result } = renderHook(() => useModal(true));
    const [visible] = result.current;
    expect(visible).toBe(true);
  });

  it('open() sets visible to true', () => {
    const { result } = renderHook(() => useModal());
    expect(result.current[0]).toBe(false);

    act(() => {
      result.current[1](); // open
    });

    expect(result.current[0]).toBe(true);
  });

  it('close() sets visible to false', () => {
    const { result } = renderHook(() => useModal(true));
    expect(result.current[0]).toBe(true);

    act(() => {
      result.current[2](); // close
    });

    expect(result.current[0]).toBe(false);
  });

  it('toggle() flips visible state', () => {
    const { result } = renderHook(() => useModal());
    expect(result.current[0]).toBe(false);

    act(() => {
      result.current[3](); // toggle
    });
    expect(result.current[0]).toBe(true);

    act(() => {
      result.current[3](); // toggle again
    });
    expect(result.current[0]).toBe(false);
  });

  it('open() is stable across renders (useCallback)', () => {
    const { result, rerender } = renderHook(() => useModal());
    const openRef = result.current[1];
    rerender({});
    expect(result.current[1]).toBe(openRef);
  });

  it('close() is stable across renders (useCallback)', () => {
    const { result, rerender } = renderHook(() => useModal());
    const closeRef = result.current[2];
    rerender({});
    expect(result.current[2]).toBe(closeRef);
  });

  it('toggle() is stable across renders (useCallback)', () => {
    const { result, rerender } = renderHook(() => useModal());
    const toggleRef = result.current[3];
    rerender({});
    expect(result.current[3]).toBe(toggleRef);
  });

  it('returns a 4-element tuple', () => {
    const { result } = renderHook(() => useModal());
    expect(result.current).toHaveLength(4);
  });
});
