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

    expect(mockPush).toHaveBeenCalledWith('/item/abc-123');
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

    expect(mockPush).toHaveBeenCalledWith('/home/portfolio');
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
