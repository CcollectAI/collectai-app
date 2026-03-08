import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

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
import { Pressable } from 'react-native';

function Trigger({ message }: { message: string }) {
  const { showToast } = useToast();
  return (
    <Pressable testID="trigger" onPress={() => showToast({ message, type: 'error' })} />
  );
}

describe('Toast a11y', () => {
  it('has alert role when displayed', () => {
    render(
      <ToastProvider>
        <Trigger message="Network error" />
      </ToastProvider>,
    );
    fireEvent.press(screen.getByTestId('trigger'));
    const toast = screen.getByRole('alert');
    expect(toast).toBeTruthy();
  });

  it('has accessibilityLabel matching the message', () => {
    render(
      <ToastProvider>
        <Trigger message="Item saved successfully" />
      </ToastProvider>,
    );
    fireEvent.press(screen.getByTestId('trigger'));
    expect(screen.getByLabelText('Item saved successfully')).toBeTruthy();
  });
});
