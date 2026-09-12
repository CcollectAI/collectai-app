/**
 * HeaderActions — the cluster must not push the screen you are already on.
 *
 * WHY (2026-09-09, found walking the release build on Android): the cluster is
 * rendered on every screen INCLUDING the three it navigates to, and each icon
 * pushed its destination unconditionally. On Settings the gear pushed a second
 * Settings — identical screen, so the tap read as a dead control, and it took
 * TWO back presses to leave. A control that silently deepens the back stack is
 * worse than one that does nothing: it breaks the user's own way out.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

// `mock`-prefixed so jest's out-of-scope guard allows the factory to close
// over them.
const mockPush = jest.fn();
const mockPath = { current: '/' };

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPath.current,
}));

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      text: '#0F172A', accent: '#40C9C6', error: '#EF4444', accentText: '#FFFFFF',
      card: '#FFF', border: '#E2E8F0', muted: '#64748B', danger: '#EF4444',
    },
  }),
}));
jest.mock('../../src/lib/settings', () => ({ useSettings: () => ({ settings: { hapticsEnabled: false } }) }));
jest.mock('../../src/providers/useAuthContext', () => ({ useAuthContext: () => ({ user: null }) }));
jest.mock('../../src/api/notificationsApi', () => ({
  getNotificationHistory: jest.fn(() => Promise.resolve({ unread_count: 0 })),
}));
// The inbox button is its own component with its own fetch; the cluster's
// behaviour is what is under test here.
jest.mock('../../src/components/InboxHeaderButton', () => ({
  InboxHeaderButton: () => null,
}));

import { HeaderActions } from '../../src/components/HeaderActions';

describe('HeaderActions on the screen it points at', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockPath.current = '/';
  });

  it('navigates to Settings from anywhere else', () => {
    mockPath.current = '/(tabs)';
    render(<HeaderActions />);
    fireEvent.press(screen.getByLabelText('Settings'));
    expect(mockPush).toHaveBeenCalledWith('/settings');
  });

  it('does NOT push Settings again when already on Settings', () => {
    mockPath.current = '/settings';
    render(<HeaderActions />);
    fireEvent.press(screen.getByLabelText('Settings'));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('treats a nested settings route as being on Settings', () => {
    mockPath.current = '/settings/blocked-users';
    render(<HeaderActions />);
    fireEvent.press(screen.getByLabelText('Settings'));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('does NOT push notifications again when already there', () => {
    mockPath.current = '/notifications';
    render(<HeaderActions />);
    fireEvent.press(screen.getByLabelText('Notifications'));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('marks the current screen’s control as selected', () => {
    mockPath.current = '/settings';
    render(<HeaderActions />);
    expect(screen.getByLabelText('Settings').props.accessibilityState).toMatchObject({ selected: true });
    expect(screen.getByLabelText('Notifications').props.accessibilityState).toMatchObject({ selected: false });
  });
});
