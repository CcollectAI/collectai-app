/**
 * The header cluster's two badges must cost ONE request per window, however
 * many headers are mounted.
 *
 * WHY (2026-09-14, Android walk): Diagnostics showed nine
 * `chat_dm_requests_v1` timeouts inside three seconds. `HeaderActions` renders
 * on five tabs plus every `ScreenHeader` screen, and a stack keeps the screens
 * under the current one mounted. `InboxHeaderButton` had no shared state at
 * all — each instance fetched on mount and polled every 30s — and the bell's
 * 60s cache was only written when a response LANDED, so headers mounting
 * together all fired before any of them could fill it.
 */
import React from 'react';
import { render, act } from '@testing-library/react-native';

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/',
}));
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: { text: '#000', accent: '#40C9C6', error: '#E00', accentText: '#FFF', danger: '#E00' },
  }),
}));
jest.mock('../../src/lib/settings', () => ({ useSettings: () => ({ settings: { hapticsEnabled: false } }) }));
const mockUser = { id: 'user-0' };
let userSeq = 0;
jest.mock('../../src/providers/useAuthContext', () => ({ useAuthContext: () => ({ user: mockUser }) }));

const mockInboxCount = jest.fn();
jest.mock('../../src/data', () => ({
  dataProvider: { getInboxUnreadCount: (...a: unknown[]) => mockInboxCount(...a) },
}));
const mockNotificationHistory = jest.fn();
jest.mock('../../src/api/notificationsApi', () => ({
  getNotificationHistory: (...a: unknown[]) => mockNotificationHistory(...a),
}));

import { InboxHeaderButton } from '../../src/components/InboxHeaderButton';
import { HeaderActions } from '../../src/components/HeaderActions';

/** A request that stays in flight until the test says otherwise. */
function pending<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

describe('header badge fan-out', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockInboxCount.mockReset();
    mockNotificationHistory.mockReset();
    // The shared counts live in module scope ON PURPOSE and are keyed by user,
    // so a new user per test starts from nothing — which also exercises the
    // keying that stops one account wearing another's badge.
    mockUser.id = `user-${++userSeq}`;
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('five mounted inbox buttons send one request, and one per poll window', async () => {
    const first = pending<number>();
    mockInboxCount.mockReturnValueOnce(first.promise).mockResolvedValue(2);
    render(
      <>
        <InboxHeaderButton />
        <InboxHeaderButton />
        <InboxHeaderButton />
        <InboxHeaderButton />
        <InboxHeaderButton />
      </>,
    );
    expect(mockInboxCount).toHaveBeenCalledTimes(1);

    await act(async () => { first.resolve(1); });
    await act(async () => { jest.advanceTimersByTime(30_000); });
    // Five intervals ticked; the shared count refreshed once.
    expect(mockInboxCount).toHaveBeenCalledTimes(2);
  });

  it('five mounted clusters ask for the notification count once', () => {
    mockNotificationHistory.mockReturnValue(pending<{ unread_count: number }>().promise);
    mockInboxCount.mockReturnValue(pending<number>().promise);
    render(
      <>
        <HeaderActions />
        <HeaderActions />
        <HeaderActions />
        <HeaderActions />
        <HeaderActions />
      </>,
    );
    expect(mockNotificationHistory).toHaveBeenCalledTimes(1);
    expect(mockInboxCount).toHaveBeenCalledTimes(1);
  });

  it('a failing count retries once per window, not on every mounted tick', async () => {
    mockInboxCount.mockRejectedValue(new Error('Request timed out after 15000ms'));
    // STAGGERED, like screens pushed one after another: mounts that start
    // together also tick together, which cannot tell "per tick" from "per window".
    render(<InboxHeaderButton />);
    await act(async () => {});
    expect(mockInboxCount).toHaveBeenCalledTimes(1);
    await act(async () => { jest.advanceTimersByTime(10_000); });
    render(<InboxHeaderButton />);
    await act(async () => {});
    await act(async () => { jest.advanceTimersByTime(10_000); });
    render(<InboxHeaderButton />);
    await act(async () => {});
    // 20s in, three mounts, one failure: still inside its window.
    expect(mockInboxCount).toHaveBeenCalledTimes(1);
    await act(async () => { jest.advanceTimersByTime(11_000); });
    expect(mockInboxCount).toHaveBeenCalledTimes(2);
  });

  it('a different account does not wear the previous account’s count', async () => {
    mockInboxCount.mockResolvedValueOnce(7);
    const first = render(<InboxHeaderButton />);
    await act(async () => {});
    expect(first.getByLabelText('Inbox, 7 unread')).toBeTruthy();
    first.unmount();

    mockUser.id = `user-${++userSeq}`;
    mockInboxCount.mockReturnValueOnce(pending<number>().promise);
    const second = render(<InboxHeaderButton />);
    // Still loading for the new account: no badge, not the old 7.
    expect(second.getByLabelText('Inbox')).toBeTruthy();
    expect(second.queryByLabelText('Inbox, 7 unread')).toBeNull();
  });
});
