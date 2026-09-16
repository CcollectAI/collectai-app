/**
 * "Add to calendar" is two writes: the OS event, then the mapping that lets
 * this app say "on your calendar" and remove it again. Neither path is
 * reachable without a device, so both are pinned here (class sweep K, 2026-09-17).
 *
 *  - mapping write fails AFTER the event exists → the member had an event this
 *    app could not see, behind the words "Failed to add", offering itself again.
 *    A second tap duplicated it.
 *  - the member deletes the event in their own calendar app → `deleteEventAsync`
 *    throws, the mapping was left in place, so the app still said "on your
 *    calendar" and every later attempt threw the same way.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const mockCreateEvent = jest.fn();
const mockDeleteEvent = jest.fn();
const mockGetEvent = jest.fn();
const mockGetCalendars = jest.fn();

jest.mock('expo-calendar', () => ({
  __esModule: true,
  createEventAsync: (...a: unknown[]) => mockCreateEvent(...a),
  deleteEventAsync: (...a: unknown[]) => mockDeleteEvent(...a),
  getEventAsync: (...a: unknown[]) => mockGetEvent(...a),
  getCalendarsAsync: (...a: unknown[]) => mockGetCalendars(...a),
  requestCalendarPermissionsAsync: async () => ({ status: 'granted' }),
  getDefaultCalendarAsync: async () => ({ id: 'cal-1' }),
  EntityTypes: { EVENT: 'event' },
  CalendarAccessLevel: { OWNER: 'owner' },
}));

jest.mock('../../src/lib/logger', () => ({
  logger: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: { CONFIDENCE_HIGH: 'CONFIDENCE_HIGH', ALERT_TRIGGERED: 'ALERT_TRIGGERED' },
}));

jest.mock('react-native', () => ({
  Platform: { OS: 'ios', select: (o: Record<string, unknown>) => o.ios },
  Alert: { alert: jest.fn() },
  Linking: { openSettings: jest.fn() },
}));

import { addToCalendar, removeFromCalendar } from '../../src/lib/calendar';

const STORAGE_KEY = '@collectai/calendar_events';

// A real in-memory store rather than the library's jest mock. jest.spyOn() on an
// already-mocked fn and then mockRestore() leaves a no-op behind, so the NEXT
// test's seeding write silently did nothing and it read an empty store — two
// failures that looked like the code and were the harness.
const store = new Map<string, string>();
const installStorage = () => {
  (AsyncStorage.getItem as jest.Mock).mockImplementation(async (k: string) => store.get(k) ?? null);
  (AsyncStorage.setItem as jest.Mock).mockImplementation(async (k: string, v: string) => { store.set(k, v); });
};

describe('addToCalendar / removeFromCalendar are not left half-done', () => {
  beforeEach(async () => {
    // restoreAllMocks, not clearAllMocks: the setItem spy from an earlier test
    // survived otherwise, so the NEXT test's seeding write was rejected and it
    // read an empty store — two green-for-the-wrong-reason failures.
    jest.clearAllMocks();
    store.clear();
    installStorage();
    mockGetCalendars.mockResolvedValue([
      { id: 'cal-1', allowsModifications: true, source: { name: 'Default' }, title: 'Cal' },
    ]);
  });

  it('rolls the OS event back when the mapping cannot be written', async () => {
    mockCreateEvent.mockResolvedValue('os-event-1');
    mockDeleteEvent.mockResolvedValue(undefined);
    (AsyncStorage.setItem as jest.Mock).mockRejectedValueOnce(new Error('disk full'));

    const res = await addToCalendar({
      eventId: 'evt-1',
      title: 'Card show',
      startDate: new Date('2026-10-01T10:00:00Z'),
    });

    expect(res.success).toBe(false);
    // The event must NOT be left in the calendar unreferenced.
    expect(mockDeleteEvent).toHaveBeenCalledWith('os-event-1');
  });

  it('says the event is really there when the rollback also fails', async () => {
    mockCreateEvent.mockResolvedValue('os-event-2');
    mockDeleteEvent.mockRejectedValue(new Error('cannot delete'));
    (AsyncStorage.setItem as jest.Mock).mockRejectedValueOnce(new Error('disk full'));

    const res = await addToCalendar({
      eventId: 'evt-2',
      title: 'Card show',
      startDate: new Date('2026-10-01T10:00:00Z'),
    });

    expect(res.success).toBe(false);
    // Telling them it was not added is what produced the duplicate.
    expect(res.error).toMatch(/Added to your calendar/i);
  });

  it('prunes the mapping when the member already deleted the event themselves', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ eventId: 'evt-3', calendarEventId: 'os-event-3', createdAt: 'now' }]),
    );
    mockDeleteEvent.mockRejectedValue(new Error('event not found'));
    mockGetEvent.mockRejectedValue(new Error('event not found')); // really gone

    const ok = await removeFromCalendar('evt-3');

    expect(ok).toBe(true);
    const left = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY)) ?? '[]');
    expect(left).toHaveLength(0);
  });

  it('keeps the mapping when the delete failed but the event is still there', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ eventId: 'evt-4', calendarEventId: 'os-event-4', createdAt: 'now' }]),
    );
    mockDeleteEvent.mockRejectedValue(new Error('permission denied'));
    mockGetEvent.mockResolvedValue({ id: 'os-event-4' }); // still in the calendar

    const ok = await removeFromCalendar('evt-4');

    expect(ok).toBe(false);
    const left = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY)) ?? '[]');
    expect(left).toHaveLength(1); // still removable later
  });
});
