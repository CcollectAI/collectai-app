/**
 * Tests for haptic intents module.
 */

import { HapticIntent, uniqueIntents, confidenceToIntent } from '../intents';

describe('uniqueIntents', () => {
  it('should return empty array for empty input', () => {
    expect(uniqueIntents([])).toEqual([]);
  });

  it('should return same array when no duplicates', () => {
    const intents = [HapticIntent.CONFIRMATION_LIGHT, HapticIntent.JUDGMENT_LOCKED];
    expect(uniqueIntents(intents)).toEqual(intents);
  });

  it('should deduplicate intents preserving order', () => {
    const intents = [
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.JUDGMENT_LOCKED,
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.ALERT_TRIGGERED,
      HapticIntent.JUDGMENT_LOCKED,
    ];
    expect(uniqueIntents(intents)).toEqual([
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.JUDGMENT_LOCKED,
      HapticIntent.ALERT_TRIGGERED,
    ]);
  });

  it('should handle single intent', () => {
    expect(uniqueIntents([HapticIntent.CONFIDENCE_HIGH])).toEqual([
      HapticIntent.CONFIDENCE_HIGH,
    ]);
  });

  it('should handle all same intents', () => {
    const intents = [
      HapticIntent.UNCERTAINTY_PRESENT,
      HapticIntent.UNCERTAINTY_PRESENT,
      HapticIntent.UNCERTAINTY_PRESENT,
    ];
    expect(uniqueIntents(intents)).toEqual([HapticIntent.UNCERTAINTY_PRESENT]);
  });
});

describe('confidenceToIntent', () => {
  it('should return CONFIDENCE_HIGH for confidence >= 0.8', () => {
    expect(confidenceToIntent(0.8)).toBe(HapticIntent.CONFIDENCE_HIGH);
    expect(confidenceToIntent(0.85)).toBe(HapticIntent.CONFIDENCE_HIGH);
    expect(confidenceToIntent(0.95)).toBe(HapticIntent.CONFIDENCE_HIGH);
    expect(confidenceToIntent(1.0)).toBe(HapticIntent.CONFIDENCE_HIGH);
  });

  it('should return UNCERTAINTY_PRESENT for confidence < 0.5', () => {
    expect(confidenceToIntent(0.0)).toBe(HapticIntent.UNCERTAINTY_PRESENT);
    expect(confidenceToIntent(0.25)).toBe(HapticIntent.UNCERTAINTY_PRESENT);
    expect(confidenceToIntent(0.49)).toBe(HapticIntent.UNCERTAINTY_PRESENT);
  });

  it('should return CONFIRMATION_LIGHT for confidence between 0.5 and 0.8', () => {
    expect(confidenceToIntent(0.5)).toBe(HapticIntent.CONFIRMATION_LIGHT);
    expect(confidenceToIntent(0.65)).toBe(HapticIntent.CONFIRMATION_LIGHT);
    expect(confidenceToIntent(0.79)).toBe(HapticIntent.CONFIRMATION_LIGHT);
  });

  it('should handle edge cases', () => {
    // Exactly at thresholds
    expect(confidenceToIntent(0.5)).toBe(HapticIntent.CONFIRMATION_LIGHT);
    expect(confidenceToIntent(0.8)).toBe(HapticIntent.CONFIDENCE_HIGH);
  });
});
