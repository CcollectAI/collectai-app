import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { Text } from 'react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));

import { ScreenErrorBoundary } from '../../src/components/ScreenErrorBoundary';

// Suppress console.error for expected throws
const origError = console.error;
beforeAll(() => { console.error = jest.fn(); });
afterAll(() => { console.error = origError; });

function GoodChild() {
  return <Text>Hello World</Text>;
}

let shouldThrow = false;
function ThrowChild() {
  if (shouldThrow) throw new Error('Test crash');
  return <Text>Child OK</Text>;
}

describe('ScreenErrorBoundary', () => {
  beforeEach(() => {
    shouldThrow = false;
  });

  it('renders children normally when no error', () => {
    render(
      <ScreenErrorBoundary>
        <GoodChild />
      </ScreenErrorBoundary>,
    );
    expect(screen.getByText('Hello World')).toBeTruthy();
  });

  it('shows fallback when child throws', () => {
    shouldThrow = true;
    render(
      <ScreenErrorBoundary>
        <ThrowChild />
      </ScreenErrorBoundary>,
    );
    expect(screen.queryByText('Child OK')).toBeNull();
    // Should show fallback UI with retry button
    expect(screen.getByText(/Retry/i)).toBeTruthy();
  });

  it('includes screenName in fallback message', () => {
    shouldThrow = true;
    render(
      <ScreenErrorBoundary screenName="Portfolio">
        <ThrowChild />
      </ScreenErrorBoundary>,
    );
    expect(screen.getByText(/Portfolio/)).toBeTruthy();
  });

  it('retry button resets error and re-renders children', () => {
    shouldThrow = true;
    render(
      <ScreenErrorBoundary>
        <ThrowChild />
      </ScreenErrorBoundary>,
    );
    // Shows fallback
    expect(screen.getByText(/Retry/i)).toBeTruthy();

    // Fix the error before retrying
    shouldThrow = false;
    fireEvent.press(screen.getByText(/Retry/i));

    // Children should render again
    expect(screen.getByText('Child OK')).toBeTruthy();
  });

  it('shows fallback again if retry still throws', () => {
    shouldThrow = true;
    render(
      <ScreenErrorBoundary>
        <ThrowChild />
      </ScreenErrorBoundary>,
    );
    // Retry without fixing the error
    fireEvent.press(screen.getByText(/Retry/i));
    // Should still show fallback
    expect(screen.getByText(/Retry/i)).toBeTruthy();
  });
});
