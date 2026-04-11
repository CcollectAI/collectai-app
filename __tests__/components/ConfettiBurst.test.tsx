/**
 * Tests for ConfettiBurst component.
 */

import React from 'react';
import { render } from '@testing-library/react-native';

// Mock accessibility
jest.mock('../../src/lib/accessibility', () => ({
  useReduceMotion: jest.fn().mockReturnValue(false),
}));

import { ConfettiBurst, ConfettiBurstRef } from '../../src/components/ConfettiBurst';

describe('ConfettiBurst', () => {
  it('renders without crashing', () => {
    expect(() => render(<ConfettiBurst />)).not.toThrow();
  });

  it('renders nothing when no particles are active', () => {
    const { toJSON } = render(<ConfettiBurst />);
    expect(toJSON()).toBeNull();
  });

  it('exposes burst method via ref', () => {
    const ref = React.createRef<ConfettiBurstRef>();
    render(<ConfettiBurst ref={ref} />);

    expect(ref.current).toBeDefined();
    expect(typeof ref.current!.burst).toBe('function');
  });

  it('exposes isAnimating via ref', () => {
    const ref = React.createRef<ConfettiBurstRef>();
    render(<ConfettiBurst ref={ref} />);

    expect(ref.current!.isAnimating).toBe(false);
  });

  it('renders with custom options', () => {
    expect(() =>
      render(
        <ConfettiBurst
          particleCount={8}
          duration={400}
          colors={['#FF0000', '#00FF00']}
          spread={60}
        />
      )
    ).not.toThrow();
  });

  it('renders with custom style', () => {
    expect(() =>
      render(<ConfettiBurst style={{ top: 100 }} />)
    ).not.toThrow();
  });
});
