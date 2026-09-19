/**
 * useOptimisticRsvp
 *
 * Provides optimistic mutation wrappers for event RSVP operations.
 *
 * On RSVP toggle:
 *  - Immediately flips the local isAttending / myRsvpStatus state
 *  - Calls the server in the background
 *  - On error, reverts the local state and RETHROWS so the screen can say so
 *
 * Works with both the events tab (list of events) and the event detail screen.
 *
 * The toast is the fix for a silent revert (2026-09-18, found by
 * `check:half-done-silence`). RSVP is a primary action on the Events tab, and a
 * failure reached the member as nothing at all: `useOptimisticMutation` catches
 * its own error and does NOT rethrow, so the screen's own `catch` never ran;
 * neither screen reads the hook's `error`; and `onRollback` logged with
 * `logger.warn`, which is STRIPPED in release builds. So the card flipped to
 * "attending", flipped back a moment later when the reload landed, and nothing
 * — not even a production log — said why. A member reads that as a mis-tap.
 *
 * The toast moved OUT of here on 2026-09-19. `useOptimisticMutation` now
 * rethrows, so the screen's own catch fires — and the screen has the better
 * copy (`userErrorMessage`) and the context to phrase it. A toast in both
 * places showed the member two.
 */

import { useOptimisticMutation } from './useOptimisticMutation';
import { dataProvider } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import logger from '@/utils/logger';

type RsvpArgs = {
  eventId: string;
  /** True if the user is currently attending (i.e. we should un-RSVP). */
  currentlyAttending: boolean;
};

// ─── For event list screens (events tab) ─────────────────────────────────────

type EventListSetter = React.Dispatch<React.SetStateAction<CollectorsEvent[]>>;

/**
 * Hook for optimistic RSVP toggling on an events list.
 * Toggles isAttending and updates attendeeCount in the local event list state.
 *
 * @param setEvents - State setter for the events array
 * @param reloadEvents - Function to reload events from server (used as rollback)
 */
export function useOptimisticRsvpList(
  setEvents: EventListSetter,
  reloadEvents: () => void,
) {
  return useOptimisticMutation<RsvpArgs>({
    mutationFn: async ({ eventId, currentlyAttending }) => {
      if (currentlyAttending) {
        await dataProvider.unrsvpEvent(eventId);
      } else {
        await dataProvider.rsvpEvent(eventId, 'going');
      }
    },

    onOptimisticUpdate: ({ eventId, currentlyAttending }) => {
      setEvents((prev) =>
        prev.map((evt) => {
          if (evt.id !== eventId) return evt;
          const willAttend = !currentlyAttending;
          return {
            ...evt,
            isAttending: willAttend,
            myRsvpStatus: willAttend ? 'going' : undefined,
            attendeeCount: Math.max(0, (evt.attendeeCount ?? 0) + (willAttend ? 1 : -1)),
          };
        }),
      );
    },

    onRollback: (_args, error) => {
      // logger.error, not warn: warn is stripped in release builds, so the one
      // place this failure was recorded did not exist in production.
      logger.error('[useOptimisticRsvpList] RSVP failed, reloading events:', error.message);
      reloadEvents();
    },
  });
}

// ─── For single event detail screen ──────────────────────────────────────────

type RsvpDetailArgs = {
  eventId: string;
  currentlyAttending: boolean;
};

type RsvpDetailSetters = {
  setRsvpStatus: React.Dispatch<React.SetStateAction<string | undefined>>;
  setEvent: React.Dispatch<React.SetStateAction<CollectorsEvent | null>>;
};

/**
 * Hook for optimistic RSVP toggling on a single event detail screen.
 * Toggles rsvpStatus state and updates the event's attendeeCount.
 *
 * @param setters - Object containing setRsvpStatus and setEvent state setters
 * @param reloadEvent - Function to reload the event from server (used as rollback)
 */
export function useOptimisticRsvpDetail(
  setters: RsvpDetailSetters,
  reloadEvent: () => void,
) {
  const { setRsvpStatus, setEvent } = setters;

  return useOptimisticMutation<RsvpDetailArgs>({
    mutationFn: async ({ eventId, currentlyAttending }) => {
      if (currentlyAttending) {
        await dataProvider.unrsvpEvent(eventId);
      } else {
        await dataProvider.rsvpEvent(eventId, 'going');
      }
    },

    onOptimisticUpdate: ({ currentlyAttending }) => {
      const willAttend = !currentlyAttending;
      setRsvpStatus(willAttend ? 'going' : undefined);
      setEvent((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          isAttending: willAttend,
          myRsvpStatus: willAttend ? 'going' : undefined,
          attendeeCount: Math.max(0, (prev.attendeeCount ?? 0) + (willAttend ? 1 : -1)),
        };
      });
    },

    onRollback: (_args, error) => {
      logger.error('[useOptimisticRsvpDetail] RSVP failed, reloading event:', error.message);
      reloadEvent();
    },
  });
}
