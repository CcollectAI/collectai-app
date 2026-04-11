/**
 * Tests for ProgressRing component.
 */

import React from 'react';
import { render } from '@testing-library/react-native';

// Mock useAppTheme
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      border: '#E2E8F0',
      accent: '#81D8D0',
    },
  }),
}));

// Mock accessibility
jest.mock('../../src/lib/accessibility', () => ({
  useReduceMotion: () => false,
  useAnimationDuration: (ms: number) => ms,
}));

// Mock react-native-svg
jest.mock('react-native-svg', () => {
  const React = require('react');
  const { View } = require('react-native');
  const MockSvg = (props: any) => React.createElement(View, props);
  const MockCircle = (props: any) => React.createElement(View, props);
  return {
    __esModule: true,
    default: MockSvg,
    Circle: MockCircle,
  };
});

import { ProgressRing } from '../../src/components/ProgressRing';

describe('ProgressRing', () => {
  it('renders without crashing', () => {
    expect(() => render(<ProgressRing progress={0.5} />)).not.toThrow();
  });

  it('renders with custom size', () => {
    expect(() =>
      render(<ProgressRing progress={0.75} size={64} />)
    ).not.toThrow();
  });

  it('renders with custom stroke width', () => {
    expect(() =>
      render(<ProgressRing progress={0.5} strokeWidth={6} />)
    ).not.toThrow();
  });

  it('renders with custom colors', () => {
    expect(() =>
      render(
        <ProgressRing
          progress={0.5}
          trackColor="#CCCCCC"
          progressColor="#FF0000"
        />
      )
    ).not.toThrow();
  });

  it('renders with progress 0', () => {
    expect(() => render(<ProgressRing progress={0} />)).not.toThrow();
  });

  it('renders with progress 1', () => {
    expect(() => render(<ProgressRing progress={1} />)).not.toThrow();
  });

  it('exposes ref methods', () => {
    const ref = React.createRef<any>();
    render(<ProgressRing ref={ref} progress={0.5} />);

    expect(ref.current).toBeDefined();
    expect(typeof ref.current.setProgress).toBe('function');
    expect(typeof ref.current.setProgressInstant).toBe('function');
  });

  it('ref setProgress does not throw', () => {
    const ref = React.createRef<any>();
    render(<ProgressRing ref={ref} progress={0.5} />);

    expect(() => ref.current.setProgress(0.8)).not.toThrow();
  });

  it('ref setProgressInstant does not throw', () => {
    const ref = React.createRef<any>();
    render(<ProgressRing ref={ref} progress={0.5} />);

    expect(() => ref.current.setProgressInstant(1.0)).not.toThrow();
  });
});
