/**
 * Haptics utility for tactile feedback.
 * Provides consistent haptic feedback patterns across the app.
 *
 * Note: Requires expo-haptics to be installed for functionality.
 * Falls back gracefully (no-op) if package is not available.
 */

import { Platform } from 'react-native';

// Optional dependency - graceful fallback if not installed
let Haptics: any = null;

try {
  Haptics = require('expo-haptics');
} catch {
  console.log('[Haptics] expo-haptics not installed - haptic feedback disabled');
}

// Check if haptics are available (iOS and some Android devices)
const hapticsAvailable = Haptics !== null && (Platform.OS === 'ios' || Platform.OS === 'android');

/**
 * Light tap feedback - for button presses and selections.
 */
export function lightTap(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Medium tap feedback - for significant actions like saves.
 */
export function mediumTap(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Heavy tap feedback - for major actions.
 */
export function heavyTap(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Success feedback - for successful operations.
 */
export function success(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Warning feedback - for warnings or confirmations.
 */
export function warning(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Error feedback - for errors or failed operations.
 */
export function error(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  } catch (e) {
    // Silently ignore errors
  }
}

/**
 * Selection feedback - for picker/selection changes.
 */
export function selection(): void {
  if (!hapticsAvailable || !Haptics) return;
  try {
    Haptics.selectionAsync();
  } catch (e) {
    // Silently ignore errors
  }
}

export default {
  lightTap,
  mediumTap,
  heavyTap,
  success,
  warning,
  error,
  selection,
};
