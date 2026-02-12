/**
 * useOptimisticRsvp
 *
 * Provides optimistic mutation wrappers for event RSVP operations.
 *
 * On RSVP toggle:
 *  - Immediately flips the local isAttending / myRsvpStatus state
 *  - Calls the server in the background
 *  - On error, reverts the local state
 *
 * Works with both the events tab (list of events) and the event detail screen.
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
      logger.warn('[useOptimisticRsvpList] RSVP failed, reloading events:', error.message);
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
      logger.warn('[useOptimisticRsvpDetail] RSVP failed, reloading event:', error.message);
      reloadEvent();
    },
  });
}
