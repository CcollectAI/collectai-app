import { renderHook } from '@testing-library/react-native';
import { usePushNotifications } from '../../src/hooks/usePushNotifications';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockPush = jest.fn();
const mockReplace = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

const mockGetPermissionsAsync = jest.fn();
const mockRequestPermissionsAsync = jest.fn();
const mockGetExpoPushTokenAsync = jest.fn();
const mockSetBadgeCountAsync = jest.fn();
const mockGetBadgeCountAsync = jest.fn();
const mockSetNotificationChannelAsync = jest.fn();

let notificationReceivedCallback: ((n: unknown) => void) | null = null;
let notificationResponseCallback: ((r: unknown) => void) | null = null;

const mockAddNotificationReceivedListener = jest.fn().mockImplementation((cb) => {
  notificationReceivedCallback = cb;
  return { remove: jest.fn() };
});

const mockAddNotificationResponseReceivedListener = jest.fn().mockImplementation((cb) => {
  notificationResponseCallback = cb;
  return { remove: jest.fn() };
});

jest.mock('expo-notifications', () => ({
  getPermissionsAsync: (...args: unknown[]) => mockGetPermissionsAsync(...args),
  requestPermissionsAsync: (...args: unknown[]) => mockRequestPermissionsAsync(...args),
  getExpoPushTokenAsync: (...args: unknown[]) => mockGetExpoPushTokenAsync(...args),
  setBadgeCountAsync: (...args: unknown[]) => mockSetBadgeCountAsync(...args),
  getBadgeCountAsync: (...args: unknown[]) => mockGetBadgeCountAsync(...args),
  setNotificationChannelAsync: (...args: unknown[]) => mockSetNotificationChannelAsync(...args),
  setNotificationHandler: jest.fn(),
  addNotificationReceivedListener: (...args: unknown[]) => mockAddNotificationReceivedListener(...args),
  addNotificationResponseReceivedListener: (...args: unknown[]) => mockAddNotificationResponseReceivedListener(...args),
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
}));

const mockRegisterPushToken = jest.fn().mockResolvedValue({});

jest.mock('../../src/api/intelligenceApi', () => ({
  recordPushImpression: jest.fn(),
  recordPushInteraction: jest.fn(),
}));

jest.mock('../../src/lib/notificationOutcomeTracker', () => ({
  trackTap: jest.fn(),
}));

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    registerPushToken: (...args: unknown[]) => mockRegisterPushToken(...args),
  },
}));

// Mock Platform / AppState / Linking via react-native barrel
const appStateListeners: Array<(state: string) => void> = [];

// Use doMock to avoid hoisting issues; the test runner still processes it before imports
jest.mock('react-native', () => {
  // Only return the subset we need — avoids TurboModule init from requireActual
  return {
    Platform: { OS: 'ios', select: jest.fn((o: Record<string, unknown>) => o.ios) },
    AppState: {
      currentState: 'active',
      addEventListener: jest.fn((_event: string, cb: (state: string) => void) => {
        appStateListeners.push(cb);
        return { remove: jest.fn() };
      }),
    },
    Linking: {
      openURL: jest.fn().mockResolvedValue(undefined),
    },
    // Stubs for any transitive imports
    StyleSheet: { create: (s: Record<string, unknown>) => s },
    NativeModules: {},
    NativeEventEmitter: jest.fn().mockImplementation(() => ({
      addListener: jest.fn(),
      removeListeners: jest.fn(),
    })),
  };
});

describe('usePushNotifications', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    notificationReceivedCallback = null;
    notificationResponseCallback = null;
    appStateListeners.length = 0;

    mockGetPermissionsAsync.mockResolvedValue({ status: 'granted' });
    mockRequestPermissionsAsync.mockResolvedValue({ status: 'granted' });
    mockGetExpoPushTokenAsync.mockResolvedValue({ data: 'ExponentPushToken[test123]' });
    mockSetBadgeCountAsync.mockResolvedValue(undefined);
    mockGetBadgeCountAsync.mockResolvedValue(3);
  });

  it('calls getPermissionsAsync during setup when userId is provided', async () => {
    renderHook(() => usePushNotifications('user-1'));

    // Allow the async setup to run
    await new Promise((r) => setTimeout(r, 0));

    expect(mockGetPermissionsAsync).toHaveBeenCalled();
  });

  it('does not run setup when userId is null', async () => {
    renderHook(() => usePushNotifications(null));

    await new Promise((r) => setTimeout(r, 0));

    expect(mockGetPermissionsAsync).not.toHaveBeenCalled();
    expect(mockAddNotificationReceivedListener).not.toHaveBeenCalled();
  });

  it('registers the push token with the backend', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    expect(mockGetExpoPushTokenAsync).toHaveBeenCalled();
    expect(mockRegisterPushToken).toHaveBeenCalledWith('ExponentPushToken[test123]', 'ios');
  });

  it('navigates to item screen on notification tap with item_id data', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    expect(notificationResponseCallback).not.toBeNull();

    // Simulate a notification tap with item_id data
    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { item_id: 'abc-123' },
          },
        },
      },
    });

    // 'abc-123' is NOT a uuid, so itemHref routes it to the CATALOG screen.
    // This asserted '/item/abc-123', which is the behaviour that produced
    // PostgREST 22P02 "invalid input syntax for type uuid" and a blank
    // "Unknown item" screen — 58/58 non-null alert_trigger_history rows were
    // catalog keys, 0 were uuids (src/lib/ids.ts). The test was pinning the bug.
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/catalog-item/[key]',
      params: { key: 'abc-123' },
    });
  });

  it('routes a UUID item_id to the owned-item screen instead', () => {
    // The other half of itemHref's contract. Without this, someone could
    // "fix" the assertion above by sending everything to the catalog.
    const { itemHref } = require('../../src/lib/ids');
    expect(itemHref('7db74bd9-7939-4929-afcf-473e76954af3')).toEqual({
      pathname: '/item/[id]',
      params: { id: '7db74bd9-7939-4929-afcf-473e76954af3' },
    });
  });

  it('navigates to deal screen on notification tap with deal_id data', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { deal_id: 'deal-456' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/purchase/deal/deal-456');
  });

  it('navigates to portfolio on value_change notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { type: 'value_change' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/(tabs)/');
  });

  it('navigates to portfolio on weekly_digest notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { type: 'weekly_digest' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/(tabs)/');
  });

  it('navigates to specific item on item_value_change notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { type: 'item_value_change', item_id: 'item-xyz' },
          },
        },
      },
    });

    // Same itemHref contract: 'item-xyz' is not a uuid, so it belongs on the
    // catalog screen. See the item_id test above.
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/catalog-item/[key]',
      params: { key: 'item-xyz' },
    });
  });

  it('navigates to event screen on event_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { event_id: 'event-123' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/events/event-123');
  });

  it('navigates to chat thread on thread_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { thread_id: 'thread-abc' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/chat/thread-abc');
  });

  it('navigates to alerts on alert_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { alert_id: 'alert-456' },
          },
        },
      },
    });

    // '/(tabs)/alerts' NEVER EXISTED — alerts was never a tab — so every push
    // carrying alert_id landed on expo-router's Unmatched screen: notification
    // arrives, user taps, 404. Caught by scripts/check-dead-nav.mjs on
    // 2026-08-08 and repointed at /notifications, which is now the single
    // inbox after app/alerts.tsx was merged into it. This test had been pinning
    // the dead route.
    expect(mockPush).toHaveBeenCalledWith('/notifications');
  });

  it('navigates to inbox on connection_request notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { connection_request_id: 'req-789' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/inbox');
  });

  it('navigates to project on project_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { project_id: 'proj-001' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/projects/proj-001');
  });

  it('navigates to category on category_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { category_id: 'pokemon_tcg' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/categories/pokemon_tcg');
  });

  it('navigates to user profile on user_id notification', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: { user_id: 'user-999' },
          },
        },
      },
    });

    expect(mockPush).toHaveBeenCalledWith('/users/user-999');
  });

  it('does nothing when notification data is empty', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    notificationResponseCallback!({
      notification: {
        request: {
          content: {
            data: {},
          },
        },
      },
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  it('clears badge count on initial setup', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    expect(mockSetBadgeCountAsync).toHaveBeenCalledWith(0);
  });

  it('sets up notification listeners when userId is provided', async () => {
    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    expect(mockAddNotificationReceivedListener).toHaveBeenCalledTimes(1);
    expect(mockAddNotificationResponseReceivedListener).toHaveBeenCalledTimes(1);
  });

  it('requests permission when existing status is not granted', async () => {
    mockGetPermissionsAsync.mockResolvedValue({ status: 'undetermined' });
    mockRequestPermissionsAsync.mockResolvedValue({ status: 'granted' });

    renderHook(() => usePushNotifications('user-1'));

    await new Promise((r) => setTimeout(r, 0));

    expect(mockRequestPermissionsAsync).toHaveBeenCalled();
  });
});
