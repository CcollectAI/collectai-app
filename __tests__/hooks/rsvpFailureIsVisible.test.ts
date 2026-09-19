/**
 * A failed optimistic mutation must REACH THE CALLER, not just the log.
 *
 * Found 2026-09-18 by `check:half-done-silence`. RSVP is a primary action on
 * the Events tab and a failure arrived as nothing at all:
 *
 *  - `useOptimisticMutation` catches its own error and does NOT rethrow, so the
 *    `catch` in `handleAttend` never ran;
 *  - neither the list screen nor the detail screen reads the hook's `error`;
 *  - `onRollback` logged with `logger.warn`, which is STRIPPED in release
 *    builds — so in production there was not even a log.
 *
 * The card flipped to "attending" and flipped back when the reload landed. A
 * member reads that as a mis-tap and taps again.
 */
// Factories are INLINE, and the mocks are read back with `jest.requireMock`.
// Referring to an outer `const` from a factory left `logger` undefined inside
// `useOptimisticMutation` — jest hoists the factory above the `const`, so it
// ran before the binding existed. `listForSaleFeeEstimate.test.ts` already
// uses this shape.
jest.mock('@/data', () => ({
  dataProvider: { rsvpEvent: jest.fn(), unrsvpEvent: jest.fn() },
}));
jest.mock('@/components/Toast', () => {
  const showToast = jest.fn();
  return { useToast: () => ({ showToast }), __showToast: showToast };
});
jest.mock('@/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() },
}));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? k }),
}));

import { renderHook, act } from '@testing-library/react-native';
import { useOptimisticRsvpList, useOptimisticRsvpDetail } from '../../src/hooks/useOptimisticRsvp';

const { dataProvider } = jest.requireMock('@/data') as {
  dataProvider: { rsvpEvent: jest.Mock; unrsvpEvent: jest.Mock };
};
const mockRsvp = dataProvider.rsvpEvent;
const mockUnrsvp = dataProvider.unrsvpEvent;
const mockShowToast = (jest.requireMock('@/components/Toast') as { __showToast: jest.Mock }).__showToast;
const mockLogger = (jest.requireMock('@/utils/logger') as { default: Record<string, jest.Mock> }).default;

beforeEach(() => {
  mockRsvp.mockReset();
  mockUnrsvp.mockReset();
  mockShowToast.mockReset();
  mockLogger.warn.mockReset();
  mockLogger.error.mockReset();
});

describe('a failed RSVP is visible to the member', () => {
  it('rejects so the screen\'s catch can speak', async () => {
    mockRsvp.mockRejectedValue(new Error('network'));
    const setEvents = jest.fn();
    const reload = jest.fn();
    const { result } = renderHook(() => useOptimisticRsvpList(setEvents, reload));

    let threw = false;
    await act(async () => {
      try {
        await result.current.mutate({ eventId: 'e1', currentlyAttending: false });
      } catch {
        threw = true;
      }
    });

    // The contract the screens rely on. While `mutate` swallowed, every
    // caller's catch was dead code — and `items.tsx` went on to show
    // "Archived" in green after a FAILED archive.
    expect(threw).toBe(true);
    // and it still rolls back first, so the list agrees with the server
    expect(reload).toHaveBeenCalled();
  });

  it('rejects from the detail-screen variant too', async () => {
    mockUnrsvp.mockRejectedValue(new Error('network'));
    const { result } = renderHook(() =>
      useOptimisticRsvpDetail(
        { setRsvpStatus: jest.fn(), setEvent: jest.fn() },
        jest.fn(),
      ),
    );

    let threw = false;
    await act(async () => {
      try {
        await result.current.mutate({ eventId: 'e1', currentlyAttending: true });
      } catch {
        threw = true;
      }
    });

    expect(threw).toBe(true);
  });

  it('records the failure with logger.error — warn is stripped in release builds', async () => {
    mockRsvp.mockRejectedValue(new Error('network'));
    const { result } = renderHook(() => useOptimisticRsvpList(jest.fn(), jest.fn()));

    await act(async () => {
      try {
        await result.current.mutate({ eventId: 'e1', currentlyAttending: false });
      } catch { /* expected */ }
    });

    expect(mockLogger.error).toHaveBeenCalled();
    expect(mockLogger.warn).not.toHaveBeenCalled();
  });

  it('does not throw when the RSVP succeeds', async () => {
    mockRsvp.mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticRsvpList(jest.fn(), jest.fn()));

    let threw = false;
    await act(async () => {
      try {
        await result.current.mutate({ eventId: 'e1', currentlyAttending: false });
      } catch {
        threw = true;
      }
    });

    expect(threw).toBe(false);
  });
});
