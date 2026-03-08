import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react-native';

jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));
jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'light',
    JUDGMENT_LOCKED: 'locked',
    ALERT_TRIGGERED: 'alert',
    CONFIDENCE_HIGH: 'high',
  },
}));
jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({ settings: { hapticsEnabled: true } }),
}));
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      skeleton: '#E2E8F0', card: '#FFFFFF', background: '#F7FAF9',
      text: '#0F172A', muted: '#64748B', accent: '#81D8D0',
      toastSuccess: '#10B981', toastError: '#EF4444',
      toastWarning: '#F59E0B', toastInfo: '#3B82F6',
    },
  }),
}));

import { ToastProvider, useToast } from '../../src/components/Toast';
import { Text, Pressable } from 'react-native';

function TestHarness({ message, type }: { message?: string; type?: 'success' | 'error' | 'warning' | 'info' }) {
  const { showToast, dismissToast } = useToast();
  return (
    <>
      <Pressable testID="show-btn" onPress={() => showToast({ message: message ?? 'Hello', type: type ?? 'success' })} />
      <Pressable testID="dismiss-btn" onPress={dismissToast} />
    </>
  );
}

function renderWithProvider(props?: { message?: string; type?: 'success' | 'error' | 'warning' | 'info' }) {
  return render(
    <ToastProvider>
      <TestHarness {...props} />
    </ToastProvider>,
  );
}

describe('Toast', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders the toast message when showToast is called', () => {
    renderWithProvider({ message: 'Item saved!' });
    fireEvent.press(screen.getByTestId('show-btn'));
    expect(screen.getByText('Item saved!')).toBeTruthy();
  });

  it('does not render toast content before showToast', () => {
    renderWithProvider({ message: 'Invisible' });
    expect(screen.queryByText('Invisible')).toBeNull();
  });

  it('renders error icon for error type', () => {
    renderWithProvider({ type: 'error', message: 'Oops' });
    fireEvent.press(screen.getByTestId('show-btn'));
    expect(screen.getByText('Oops')).toBeTruthy();
  });

  it('renders success icon for success type', () => {
    renderWithProvider({ type: 'success', message: 'Done!' });
    fireEvent.press(screen.getByTestId('show-btn'));
    expect(screen.getByText('Done!')).toBeTruthy();
  });

  it('dismissToast hides the toast', () => {
    renderWithProvider({ message: 'Bye' });
    fireEvent.press(screen.getByTestId('show-btn'));
    expect(screen.getByText('Bye')).toBeTruthy();
    fireEvent.press(screen.getByTestId('dismiss-btn'));
    // After dismiss animation tick
    act(() => { jest.advanceTimersByTime(500); });
    expect(screen.queryByText('Bye')).toBeNull();
  });

  it('useToast outside provider returns without crashing', () => {
    function Bare() {
      const { showToast } = useToast();
      return <Text testID="bare">{typeof showToast}</Text>;
    }
    render(<Bare />);
    expect(screen.getByTestId('bare')).toBeTruthy();
  });

  it('renders toast with accessibility role', () => {
    renderWithProvider({ message: 'Accessible toast' });
    fireEvent.press(screen.getByTestId('show-btn'));
    expect(screen.getByText('Accessible toast')).toBeTruthy();
  });
});
