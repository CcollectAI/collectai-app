/**
 * Haptics Module
 * Semantic haptic feedback system for CcollectAI.
 */

export { HapticIntent, uniqueIntents, confidenceToIntent } from './intents';
export { fireHaptic, fireHaptics, clearDebounceState } from './driver';
export type { FireHapticOptions } from './driver';
