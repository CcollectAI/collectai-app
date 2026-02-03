/**
 * Haptic Intent Definitions
 * Semantic haptic feedback intents for meaningful UI state changes.
 */

export enum HapticIntent {
  /** Light confirmation for toggles and selections */
  CONFIRMATION_LIGHT = 'CONFIRMATION_LIGHT',
  /** Strong feedback when saving/committing actions */
  JUDGMENT_LOCKED = 'JUDGMENT_LOCKED',
  /** Confident scan result (>= 0.8) */
  CONFIDENCE_HIGH = 'CONFIDENCE_HIGH',
  /** Uncertain scan result (< 0.5) */
  UNCERTAINTY_PRESENT = 'UNCERTAINTY_PRESENT',
  /** Error or critical alert */
  ALERT_TRIGGERED = 'ALERT_TRIGGERED',
}

/**
 * Deduplicate an array of intents, preserving order.
 */
export function uniqueIntents(intents: HapticIntent[]): HapticIntent[] {
  const seen = new Set<HapticIntent>();
  return intents.filter((intent) => {
    if (seen.has(intent)) return false;
    seen.add(intent);
    return true;
  });
}

/**
 * Map a confidence score to the appropriate haptic intent.
 * @param confidence - Value between 0 and 1
 * @returns HapticIntent based on confidence threshold
 */
export function confidenceToIntent(confidence: number): HapticIntent {
  if (confidence >= 0.8) return HapticIntent.CONFIDENCE_HIGH;
  if (confidence < 0.5) return HapticIntent.UNCERTAINTY_PRESENT;
  return HapticIntent.CONFIRMATION_LIGHT;
}
