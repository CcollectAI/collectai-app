/**
 * A toast fired while a native Modal is open must render INSIDE the modal:
 * on Android a Modal is its own window and the root toast is drawn under it.
 * Walked 2026-10-15: Edit Profile's "Username may only contain letters,
 * numbers and underscores" was toasted and invisible.
 */
import React from 'react';
import { View, Pressable, Text } from 'react-native';
import { render, fireEvent, act, within } from '@testing-library/react-native';

jest.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) }));
jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('@/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: {} }));
jest.mock('@/lib/settings', () => ({ useSettings: () => ({ settings: { hapticsEnabled: false } }) }));
jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { toastSuccess: '#111', toastError: '#111', toastWarning: '#111', toastInfo: '#111' } }),
}));

import { ToastProvider, ToastHost, useToast } from '@/components/Toast';

function Screen({ modalOpen }: { modalOpen: boolean }) {
  const { showToast } = useToast();
  return (
    <View>
      <Pressable onPress={() => showToast({ message: 'Username may only contain letters' })}><Text>save</Text></Pressable>
      {modalOpen ? <View testID="modal"><ToastHost /></View> : null}
    </View>
  );
}

it('renders the toast inside the open modal, not under it', () => {
  const { getByText, getByTestId, getAllByText } = render(<ToastProvider><Screen modalOpen /></ToastProvider>);
  act(() => { fireEvent.press(getByText('save')); });
  expect(getAllByText('Username may only contain letters')).toHaveLength(1);
  expect(within(getByTestId('modal')).getByText('Username may only contain letters')).toBeTruthy();
});

it('renders at the root when no modal is open', () => {
  const { getByText, getAllByText, queryByTestId } = render(<ToastProvider><Screen modalOpen={false} /></ToastProvider>);
  act(() => { fireEvent.press(getByText('save')); });
  expect(queryByTestId('modal')).toBeNull();
  expect(getAllByText('Username may only contain letters')).toHaveLength(1);
});
