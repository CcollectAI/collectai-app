/**
 * Calendar utility for native calendar integration.
 * Handles adding events to device calendar and setting reminders.
 *
 * Note: Requires expo-calendar and expo-notifications to be installed for full functionality.
 * Falls back gracefully if packages are not available.
 */

import { Platform, Alert, Linking } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';

import type { ExpoCalendarEntry } from '@/../types/api';

// Optional dependencies - graceful fallback if not installed
 
let Calendar: Record<string, any> | null = null;
 
let Notifications: Record<string, any> | null = null;

try {
  Calendar = require('expo-calendar');
} catch {
  logger.info('[Calendar] expo-calendar not installed - calendar features disabled');
}

try {
  Notifications = require('expo-notifications');
} catch {
  logger.info('[Calendar] expo-notifications not installed - reminder features disabled');
}

const CALENDAR_STORAGE_KEY = '@collectai/calendar_events';
const REMINDERS_STORAGE_KEY = '@collectai/event_reminders';

interface StoredCalendarEvent {
  eventId: string;
  calendarEventId: string;
  createdAt: string;
}

interface StoredReminder {
  eventId: string;
  notificationId: string;
  scheduledFor: string;
}

/**
 * Check if calendar features are available
 */
export function isCalendarAvailable(): boolean {
  return Calendar !== null;
}

/**
 * Check if notification features are available
 */
export function isNotificationsAvailable(): boolean {
  return Notifications !== null;
}

/**
 * Request calendar permissions
 */
export async function requestCalendarPermission(): Promise<boolean> {
  if (!Calendar) {
    logger.warn('[Calendar] expo-calendar not installed');
    return false;
  }
  const { status } = await Calendar.requestCalendarPermissionsAsync();
  return status === 'granted';
}

/**
 * Request notification permissions
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!Notifications) {
    logger.warn('[Calendar] expo-notifications not installed');
    return false;
  }
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

/**
 * Get the default calendar ID for the platform
 */
async function getDefaultCalendarId(): Promise<string | null> {
  if (!Calendar) return null;

  try {
    const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);

    if (Platform.OS === 'ios') {
      // iOS: Prefer iCloud calendar, then local calendar
      const iCloudCalendar = calendars.find(
        (cal: ExpoCalendarEntry) => cal.source?.type === 'caldav' && cal.allowsModifications
      );
      if (iCloudCalendar) return iCloudCalendar.id;

      // Fallback to local calendar
      const localCalendar = calendars.find(
        (cal: ExpoCalendarEntry) => cal.source?.type === 'local' && cal.allowsModifications
      );
      if (localCalendar) return localCalendar.id;

      // Any modifiable calendar
      const modifiable = calendars.find((cal: ExpoCalendarEntry) => cal.allowsModifications);
      return modifiable?.id || null;
    }

    // Android: Prefer primary calendar
    const primaryCalendar = calendars.find(
      (cal: ExpoCalendarEntry) => cal.isPrimary && cal.allowsModifications
    );
    if (primaryCalendar) return primaryCalendar.id;

    // Fallback to first modifiable calendar
    const modifiableCalendar = calendars.find((cal: ExpoCalendarEntry) => cal.allowsModifications);
    return modifiableCalendar?.id || null;
  } catch (error) {
    logger.warn('[Calendar] Error getting calendars:', error);
    return null;
  }
}

/**
 * Add an event to the device calendar
 */
export async function addToCalendar(params: {
  eventId: string;
  title: string;
  startDate: Date;
  endDate?: Date;
  location?: string;
  notes?: string;
  url?: string;
}): Promise<{ success: boolean; calendarEventId?: string; error?: string }> {
  if (!Calendar) {
    Alert.alert(
      'Calendar Not Available',
      'Calendar features require installing expo-calendar. Please run: npx expo install expo-calendar',
    );
    return { success: false, error: 'expo-calendar not installed' };
  }

  try {
    const hasPermission = await requestCalendarPermission();
    if (!hasPermission) {
      Alert.alert(
        'Calendar Access Required',
        'Please enable calendar access in Settings to add events.',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Open Settings', onPress: () => Linking.openSettings() },
        ]
      );
      return { success: false, error: 'Permission denied' };
    }

    const calendarId = await getDefaultCalendarId();
    if (!calendarId) {
      return { success: false, error: 'No calendar found' };
    }

    const endDate = params.endDate || new Date(params.startDate.getTime() + 60 * 60 * 1000); // Default 1 hour

    const calendarEventId = await Calendar.createEventAsync(calendarId, {
      title: params.title,
      startDate: params.startDate,
      endDate: endDate,
      location: params.location,
      notes: params.notes,
      url: params.url,
      alarms: [
        { relativeOffset: -60 }, // 1 hour before
        { relativeOffset: -1440 }, // 1 day before
      ],
    });

    // Store the mapping
    await storeCalendarEvent({
      eventId: params.eventId,
      calendarEventId,
      createdAt: new Date().toISOString(),
    });

    fireHaptic(HapticIntent.CONFIDENCE_HIGH);
    return { success: true, calendarEventId };
  } catch (error: unknown) {
    logger.warn('[Calendar] Error adding event:', error);
    fireHaptic(HapticIntent.ALERT_TRIGGERED);
    return { success: false, error: error instanceof Error ? error.message : 'Failed to add event' };
  }
}

/**
 * Check if an event has been added to calendar
 */
export async function isEventInCalendar(eventId: string): Promise<boolean> {
  try {
    const stored = await getStoredCalendarEvents();
    return stored.some((e) => e.eventId === eventId);
  } catch {
    return false;
  }
}

/**
 * Remove an event from calendar
 */
export async function removeFromCalendar(eventId: string): Promise<boolean> {
  if (!Calendar) return false;

  try {
    const stored = await getStoredCalendarEvents();
    const event = stored.find((e) => e.eventId === eventId);

    if (event) {
      await Calendar.deleteEventAsync(event.calendarEventId);
      const updated = stored.filter((e) => e.eventId !== eventId);
      await AsyncStorage.setItem(CALENDAR_STORAGE_KEY, JSON.stringify(updated));
      fireHaptic(HapticIntent.CONFIDENCE_HIGH);
      return true;
    }
    return false;
  } catch (error) {
    logger.warn('[Calendar] Error removing event:', error);
    return false;
  }
}

/**
 * Schedule a push notification reminder
 */
export async function scheduleReminder(params: {
  eventId: string;
  title: string;
  body: string;
  triggerDate: Date;
}): Promise<{ success: boolean; notificationId?: string; error?: string }> {
  if (!Notifications) {
    Alert.alert(
      'Notifications Not Available',
      'Reminder features require installing expo-notifications. Please run: npx expo install expo-notifications',
    );
    return { success: false, error: 'expo-notifications not installed' };
  }

  try {
    const hasPermission = await requestNotificationPermission();
    if (!hasPermission) {
      Alert.alert(
        'Notifications Required',
        'Please enable notifications in Settings to receive reminders.',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Open Settings', onPress: () => Linking.openSettings() },
        ]
      );
      return { success: false, error: 'Permission denied' };
    }

    // Don't schedule if date is in the past
    if (params.triggerDate.getTime() < Date.now()) {
      return { success: false, error: 'Event has already passed' };
    }

    // iOS uses date trigger, Android needs seconds from now
    const trigger = Platform.OS === 'ios'
      ? { date: params.triggerDate }
      : { seconds: Math.max(1, Math.floor((params.triggerDate.getTime() - Date.now()) / 1000)) };

    const notificationId = await Notifications.scheduleNotificationAsync({
      content: {
        title: params.title,
        body: params.body,
        sound: true,
        data: { eventId: params.eventId },
      },
      trigger,
    });

    // Store the reminder
    await storeReminder({
      eventId: params.eventId,
      notificationId,
      scheduledFor: params.triggerDate.toISOString(),
    });

    fireHaptic(HapticIntent.CONFIDENCE_HIGH);
    return { success: true, notificationId };
  } catch (error: unknown) {
    logger.warn('[Calendar] Error scheduling reminder:', error);
    fireHaptic(HapticIntent.ALERT_TRIGGERED);
    return { success: false, error: error instanceof Error ? error.message : 'Failed to schedule reminder' };
  }
}

/**
 * Cancel a scheduled reminder
 */
export async function cancelReminder(eventId: string): Promise<boolean> {
  if (!Notifications) return false;

  try {
    const stored = await getStoredReminders();
    const reminder = stored.find((r) => r.eventId === eventId);

    if (reminder) {
      await Notifications.cancelScheduledNotificationAsync(reminder.notificationId);
      const updated = stored.filter((r) => r.eventId !== eventId);
      await AsyncStorage.setItem(REMINDERS_STORAGE_KEY, JSON.stringify(updated));
      fireHaptic(HapticIntent.CONFIDENCE_HIGH);
      return true;
    }
    return false;
  } catch (error) {
    logger.warn('[Calendar] Error canceling reminder:', error);
    return false;
  }
}

/**
 * Check if an event has a reminder set
 */
export async function hasReminder(eventId: string): Promise<boolean> {
  try {
    const stored = await getStoredReminders();
    return stored.some((r) => r.eventId === eventId);
  } catch {
    return false;
  }
}

// Storage helpers
async function getStoredCalendarEvents(): Promise<StoredCalendarEvent[]> {
  try {
    const data = await AsyncStorage.getItem(CALENDAR_STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

async function storeCalendarEvent(event: StoredCalendarEvent): Promise<void> {
  const existing = await getStoredCalendarEvents();
  const updated = [...existing.filter((e) => e.eventId !== event.eventId), event];
  await AsyncStorage.setItem(CALENDAR_STORAGE_KEY, JSON.stringify(updated));
}

async function getStoredReminders(): Promise<StoredReminder[]> {
  try {
    const data = await AsyncStorage.getItem(REMINDERS_STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

async function storeReminder(reminder: StoredReminder): Promise<void> {
  const existing = await getStoredReminders();
  const updated = [...existing.filter((r) => r.eventId !== reminder.eventId), reminder];
  await AsyncStorage.setItem(REMINDERS_STORAGE_KEY, JSON.stringify(updated));
}

/**
 * Calculate countdown to an event
 */
export function getCountdown(targetDate: Date): {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  isPast: boolean;
  isToday: boolean;
  isTomorrow: boolean;
  formatted: string;
} {
  const now = new Date();
  const diff = targetDate.getTime() - now.getTime();
  const isPast = diff < 0;

  const absDiff = Math.abs(diff);
  const days = Math.floor(absDiff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((absDiff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((absDiff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((absDiff % (1000 * 60)) / 1000);

  // Check if today or tomorrow
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart.getTime() + 24 * 60 * 60 * 1000);
  const tomorrowEnd = new Date(tomorrowStart.getTime() + 24 * 60 * 60 * 1000);

  const isToday = targetDate >= todayStart && targetDate < tomorrowStart;
  const isTomorrow = targetDate >= tomorrowStart && targetDate < tomorrowEnd;

  // Format string
  let formatted: string;
  if (isPast) {
    formatted = 'Event ended';
  } else if (isToday) {
    formatted = `Today at ${targetDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } else if (isTomorrow) {
    formatted = `Tomorrow at ${targetDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } else if (days === 0) {
    formatted = `${hours}h ${minutes}m`;
  } else if (days === 1) {
    formatted = `1 day ${hours}h`;
  } else if (days < 7) {
    formatted = `${days} days`;
  } else {
    const weeks = Math.floor(days / 7);
    formatted = weeks === 1 ? '1 week' : `${weeks} weeks`;
  }

  return { days, hours, minutes, seconds, isPast, isToday, isTomorrow, formatted };
}

/**
 * Parse event date string to Date object
 * Supports formats: "2026-02-15", "2026-02-15T14:00:00"
 */
/**
 * Timezone abbreviation → offset from UTC in minutes. Curated to the common,
 * low-ambiguity zones this app's events actually use (mostly European), so an
 * event labelled "19:30 CET" renders at the correct instant in the *viewer's*
 * local time rather than being shown as a raw 19:30 everywhere. Unknown or
 * genuinely ambiguous abbreviations fall through to "treat as local".
 */
const TZ_OFFSET_MIN: Record<string, number> = {
  UTC: 0, GMT: 0, WET: 0,
  BST: 60, WEST: 60, CET: 60, WAT: 60,
  CEST: 120, EET: 120, SAST: 120,
  EEST: 180, MSK: 180, EAT: 180, TRT: 180,
  GST: 240,
  PKT: 300,
  ICT: 420, WIB: 420,
  HKT: 480, SGT: 480, AWST: 480, PHT: 480,
  JST: 540, KST: 540,
  ACST: 570,
  AEST: 600,
  AEDT: 660,
  NZST: 720,
  NZDT: 780,
  // Americas (US zones assumed for CST/EST etc. — this app's audience is Western)
  EDT: -240,
  EST: -300, CDT: -300,
  CST: -360, MDT: -360,
  MST: -420, PDT: -420,
  PST: -480,
  AKST: -540,
  HST: -600,
};

export function parseEventDate(dateStr: string, timeStr?: string): Date {
  if (dateStr.includes('T')) {
    return new Date(dateStr);
  }

  if (timeStr) {
    // Parse time like "14:00", "2:00 PM", "12:00 CET".
    const trimmed = timeStr.trim();
    const isAmPm = /(AM|PM)$/i.test(trimmed);
    // A trailing timezone abbreviation (not AM/PM) tells us the event's zone.
    const tzMatch = isAmPm ? null : trimmed.match(/\b([A-Z]{2,4})$/);
    const tzAbbr = tzMatch ? tzMatch[1].toUpperCase() : null;

    const cleanTime = trimmed.replace(/\s*(AM|PM|[A-Z]{2,4})$/i, '').trim();
    const [rawHours, rawMinutes] = cleanTime.split(':').map(Number);
    const isPM = /PM$/i.test(trimmed);
    const hours = isPM && rawHours !== 12 ? rawHours + 12 : rawHours;
    const minutes = rawMinutes || 0;

    if (tzAbbr && tzAbbr in TZ_OFFSET_MIN) {
      // The wall-clock time is in the event's timezone → convert to the UTC
      // instant so the app renders it in the viewer's local time (and buckets
      // it on the correct local day).
      const [y, mo, d] = dateStr.split('-').map(Number);
      const utcMs = Date.UTC(y, mo - 1, d, hours, minutes) - TZ_OFFSET_MIN[tzAbbr] * 60000;
      return new Date(utcMs);
    }

    // No known timezone — treat the time as the viewer's local time (best effort).
    return new Date(`${dateStr}T${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`);
  }

  return new Date(`${dateStr}T00:00:00`);
}

export default {
  isCalendarAvailable,
  isNotificationsAvailable,
  requestCalendarPermission,
  requestNotificationPermission,
  addToCalendar,
  isEventInCalendar,
  removeFromCalendar,
  scheduleReminder,
  cancelReminder,
  hasReminder,
  getCountdown,
  parseEventDate,
};
