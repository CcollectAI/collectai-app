/**
 * Tests for useConfetti hook.
 */

import { renderHook, act } from '@testing-library/react-native';

// Mock accessibility
jest.mock('../../src/lib/accessibility', () => ({
  useReduceMotion: jest.fn().mockReturnValue(false),
}));

import { useConfetti } from '../../src/hooks/useConfetti';

describe('useConfetti', () => {
  it('should start with no particles and not animating', () => {
    const { result } = renderHook(() => useConfetti());

    expect(result.current.particles).toEqual([]);
    expect(result.current.isAnimating).toBe(false);
    expect(typeof result.current.burst).toBe('function');
    expect(typeof result.current.getParticleStyle).toBe('function');
  });

  it('should create particles on burst', () => {
    const { result } = renderHook(() => useConfetti({ particleCount: 6 }));

    act(() => {
      result.current.burst();
    });

    expect(result.current.particles.length).toBe(6);
    expect(result.current.isAnimating).toBe(true);
  });

  it('should use default particle count of 12', () => {
    const { result } = renderHook(() => useConfetti());

    act(() => {
      result.current.burst();
    });

    expect(result.current.particles.length).toBe(12);
  });

  it('should assign colors to particles', () => {
    const colors = ['#FF0000', '#00FF00'];
    const { result } = renderHook(() =>
      useConfetti({ particleCount: 4, colors })
    );

    act(() => {
      result.current.burst();
    });

    expect(result.current.particles[0].color).toBe('#FF0000');
    expect(result.current.particles[1].color).toBe('#00FF00');
    expect(result.current.particles[2].color).toBe('#FF0000');
    expect(result.current.particles[3].color).toBe('#00FF00');
  });

  it('should not burst when already animating', () => {
    const { result } = renderHook(() => useConfetti({ particleCount: 4 }));

    act(() => {
      result.current.burst();
    });

    const firstParticles = result.current.particles;

    act(() => {
      result.current.burst(); // should be no-op
    });

    // Particles should be the same (no re-creation)
    expect(result.current.particles).toBe(firstParticles);
  });

  it('should not burst when reduce motion is enabled', () => {
    const { useReduceMotion } = require('../../src/lib/accessibility');
    (useReduceMotion as jest.Mock).mockReturnValue(true);

    const { result } = renderHook(() => useConfetti());

    act(() => {
      result.current.burst();
    });

    expect(result.current.particles).toEqual([]);
    expect(result.current.isAnimating).toBe(false);

    // Reset
    (useReduceMotion as jest.Mock).mockReturnValue(false);
  });

  it('getParticleStyle should return valid style object', () => {
    const { result } = renderHook(() => useConfetti({ particleCount: 1 }));

    act(() => {
      result.current.burst();
    });

    const style = result.current.getParticleStyle(result.current.particles[0]);
    expect(style.position).toBe('absolute');
    expect(style.width).toBe(8);
    expect(style.height).toBe(8);
    expect(style.borderRadius).toBe(4);
  });

  it('each particle should have unique ids', () => {
    const { result } = renderHook(() => useConfetti({ particleCount: 5 }));

    act(() => {
      result.current.burst();
    });

    const ids = result.current.particles.map((p) => p.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(5);
  });
});
