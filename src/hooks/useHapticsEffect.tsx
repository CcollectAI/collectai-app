/**
 * useHapticsEffect Hook
 * Fire haptics in response to state changes.
 */

import { useEffect, useRef } from 'react';
import { HapticIntent, confidenceToIntent, fireHaptic } from '../haptics';
import { useSettings } from '../lib/settings';

export type UseHapticsEffectOptions = {
  /** Haptic intents to fire */
  intents: HapticIntent[];
  /** Stable key to track changes - haptics fire when this changes */
  stableKey: string | number | null | undefined;
  /** Skip firing haptics */
  skip?: boolean;
};

/**
 * Fire haptics once when stableKey changes.
 */
export function useHapticsEffect(options: UseHapticsEffectOptions): void {
  const { intents, stableKey, skip = false } = options;
  const { settings } = useSettings();
  const previousKey = useRef<string | number | null | undefined>(undefined);
  const isFirstRender = useRef(true);

  useEffect(() => {
    // Skip on first render
    if (isFirstRender.current) {
      isFirstRender.current = false;
      previousKey.current = stableKey;
      return;
    }

    // Skip if key hasn't changed
    if (previousKey.current === stableKey) return;
    previousKey.current = stableKey;

    // Skip if disabled
    if (skip) return;

    // Check user settings for haptics
    const hapticsEnabled = settings.hapticsEnabled ?? true;
    if (!hapticsEnabled) return;

    // Fire all intents
    for (const intent of intents) {
      fireHaptic(intent, { enabled: true });
    }
  }, [intents, stableKey, skip, settings.hapticsEnabled]);
}

export type UseConfidenceHapticOptions = {
  /** Skip firing haptic */
  skip?: boolean;
};

/**
 * Convenience hook to fire confidence-based haptic feedback.
 * @param confidence - Confidence score (0-1)
 * @param stableKey - Key to track changes
 * @param options - Additional options
 */
export function useConfidenceHaptic(
  confidence: number | null | undefined,
  stableKey: string | number | null | undefined,
  options: UseConfidenceHapticOptions = {}
): void {
  const { skip = false } = options;

  const intent = confidence != null ? confidenceToIntent(confidence) : null;

  useHapticsEffect({
    intents: intent ? [intent] : [],
    stableKey,
    skip: skip || confidence == null,
  });
}
