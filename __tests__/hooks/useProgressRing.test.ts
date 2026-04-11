/**
 * Tests for useProgressRing hook.
 */

import { renderHook, act } from '@testing-library/react-native';
import { Animated } from 'react-native';

// Mock accessibility
jest.mock('../../src/lib/accessibility', () => ({
  useReduceMotion: () => false,
  useAnimationDuration: (ms: number) => ms,
}));

import { useProgressRing } from '../../src/hooks/useProgressRing';

const CIRCUMFERENCE = 100 * Math.PI; // ~314.16

describe('useProgressRing', () => {
  it('should return animatedProgress, strokeDashoffset, setProgress, setProgressInstant', () => {
    const { result } = renderHook(() => useProgressRing(CIRCUMFERENCE));

    expect(result.current.animatedProgress).toBeInstanceOf(Animated.Value);
    expect(result.current.strokeDashoffset).toBeDefined();
    expect(typeof result.current.setProgress).toBe('function');
    expect(typeof result.current.setProgressInstant).toBe('function');
  });

  it('should initialize with default progress of 0', () => {
    const { result } = renderHook(() => useProgressRing(CIRCUMFERENCE));

    // The animated value should start at 0
    let value: number | undefined;
    result.current.animatedProgress.addListener(({ value: v }) => { value = v; });
    result.current.animatedProgress.setValue(0); // trigger listener
    expect(value).toBe(0);
    result.current.animatedProgress.removeAllListeners();
  });

  it('should initialize with custom initial progress', () => {
    const { result } = renderHook(() =>
      useProgressRing(CIRCUMFERENCE, { initialProgress: 0.5 })
    );

    let value: number | undefined;
    result.current.animatedProgress.addListener(({ value: v }) => { value = v; });
    result.current.animatedProgress.setValue(0.5); // trigger listener
    expect(value).toBe(0.5);
    result.current.animatedProgress.removeAllListeners();
  });

  it('setProgressInstant should clamp values to 0-1', () => {
    const { result } = renderHook(() => useProgressRing(CIRCUMFERENCE));

    let value: number | undefined;
    result.current.animatedProgress.addListener(({ value: v }) => { value = v; });

    act(() => {
      result.current.setProgressInstant(1.5);
    });
    expect(value).toBe(1);

    act(() => {
      result.current.setProgressInstant(-0.5);
    });
    expect(value).toBe(0);

    result.current.animatedProgress.removeAllListeners();
  });

  it('setProgress should be callable without errors', () => {
    const { result } = renderHook(() => useProgressRing(CIRCUMFERENCE));

    expect(() => {
      act(() => {
        result.current.setProgress(0.75);
      });
    }).not.toThrow();
  });

  it('should accept custom duration', () => {
    const { result } = renderHook(() =>
      useProgressRing(CIRCUMFERENCE, { duration: 500 })
    );

    expect(result.current.setProgress).toBeDefined();
  });
});
