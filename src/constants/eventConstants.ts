/**
 * Shared event kind constants -- icon mapping and display labels.
 * Extracted to avoid duplication across events tab, event detail, and create-event screens.
 */

import type { Ionicons } from '@expo/vector-icons';
import type { EventKind } from '@/data/events';

/**
 * Icon names (Ionicons) for each event kind.
 * Used in event cards, kind badges, and the create-event form.
 */
export const KIND_ICON: Record<EventKind, keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
  convention: 'map-outline',
  release: 'rocket-outline',
};

/**
 * Human-readable labels for each event kind.
 * Used in event cards, meta lines, calendar notes, and reminders.
 */
export const KIND_LABEL: Record<EventKind, string> = {
  collection_drop: 'Collection drop',
  meetup: 'Meetup',
  stream: 'Twitch stream',
  convention: 'Convention',
  release: 'New release',
};
