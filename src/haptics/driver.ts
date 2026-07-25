/**
 * Haptic Driver
 * Maps semantic intents to expo-haptics calls with debouncing.
 */

import { Platform } from 'react-native';
import { HapticIntent, uniqueIntents } from './intents';
import { logger } from '@/lib/logger';

// Optional dependency - graceful fallback if not installed
 
let Haptics: Record<string, any> | null = null;

try {
  Haptics = require('expo-haptics');
} catch (e) {
  logger.error('[silent-catch] driver.ts:15:', e);
  // expo-haptics not installed - haptic feedback disabled
}

const hapticsAvailable = Haptics !== null && (Platform.OS === 'ios' || Platform.OS === 'android');

// Debounce tracking
const lastFiredAt = new Map<HapticIntent, number>();

// Debounce durations (ms)
const DEBOUNCE_STANDARD = 800;
const DEBOUNCE_ALERT = 2500;

function getDebounceMs(intent: HapticIntent): number {
  return intent === HapticIntent.ALERT_TRIGGERED ? DEBOUNCE_ALERT : DEBOUNCE_STANDARD;
}

function shouldDebounce(intent: HapticIntent): boolean {
  const now = Date.now();
  const lastTime = lastFiredAt.get(intent) ?? 0;
  const debounceMs = getDebounceMs(intent);
  return now - lastTime < debounceMs;
}

function recordFire(intent: HapticIntent): void {
  lastFiredAt.set(intent, Date.now());
}

/**
 * Execute the haptic pattern for an intent.
 */
async function executeHaptic(intent: HapticIntent): Promise<void> {
  if (!hapticsAvailable || !Haptics) return;

  try {
    switch (intent) {
      case HapticIntent.CONFIRMATION_LIGHT:
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;

      case HapticIntent.JUDGMENT_LOCKED:
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        break;

      case HapticIntent.CONFIDENCE_HIGH:
        // Double tap: medium + light
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        await new Promise((r) => setTimeout(r, 80));
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;

      case HapticIntent.UNCERTAINTY_PRESENT:
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;

      case HapticIntent.ALERT_TRIGGERED:
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        break;
    }
  } catch (e) {
    logger.error('[silent-catch] driver.ts:74:', e);
    // Silently ignore errors
  }
}

export type FireHapticOptions = {
  /** Whether haptics are enabled (from user settings) */
  enabled?: boolean;
  /** Force fire, bypassing debounce */
  force?: boolean;
};

/**
 * Fire a single haptic intent.
 */
export async function fireHaptic(
  intent: HapticIntent,
  options: FireHapticOptions = {}
): Promise<void> {
  const { enabled = true, force = false } = options;

  if (!enabled) return;
  if (!force && shouldDebounce(intent)) return;

  recordFire(intent);
  await executeHaptic(intent);
}

/**
 * Fire multiple haptic intents (deduplicated).
 */
export async function fireHaptics(
  intents: HapticIntent[],
  options: FireHapticOptions = {}
): Promise<void> {
  const unique = uniqueIntents(intents);
  for (const intent of unique) {
    await fireHaptic(intent, options);
  }
}

/**
 * Clear debounce state (useful for testing).
 */
export function clearDebounceState(): void {
  lastFiredAt.clear();
}
