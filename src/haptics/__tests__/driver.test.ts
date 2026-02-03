/**
 * Tests for haptic driver module.
 */

import { HapticIntent } from '../intents';
import { fireHaptic, fireHaptics, clearDebounceState } from '../driver';

// Mock expo-haptics
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn().mockResolvedValue(undefined),
  notificationAsync: jest.fn().mockResolvedValue(undefined),
  ImpactFeedbackStyle: {
    Light: 'Light',
    Medium: 'Medium',
    Heavy: 'Heavy',
  },
  NotificationFeedbackType: {
    Success: 'Success',
    Warning: 'Warning',
    Error: 'Error',
  },
}));

// Mock react-native Platform
jest.mock('react-native', () => ({
  Platform: {
    OS: 'ios',
  },
}));

describe('fireHaptic', () => {
  beforeEach(() => {
    clearDebounceState();
    jest.clearAllMocks();
  });

  it('should not fire when enabled is false', async () => {
    const Haptics = require('expo-haptics');
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: false });
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('should fire when enabled is true', async () => {
    const Haptics = require('expo-haptics');
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: true });
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Light');
  });

  it('should debounce repeated calls', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    // Only first call should go through
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);
  });

  it('should bypass debounce when force is true', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { force: true });
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { force: true });

    expect(Haptics.impactAsync).toHaveBeenCalledTimes(3);
  });

  it('should use correct haptic for JUDGMENT_LOCKED', async () => {
    const Haptics = require('expo-haptics');
    await fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('Success');
  });

  it('should use correct haptic for ALERT_TRIGGERED', async () => {
    const Haptics = require('expo-haptics');
    await fireHaptic(HapticIntent.ALERT_TRIGGERED);
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('Warning');
  });

  it('should fire double tap for CONFIDENCE_HIGH', async () => {
    const Haptics = require('expo-haptics');
    await fireHaptic(HapticIntent.CONFIDENCE_HIGH);

    // Medium + Light (double tap)
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Medium');
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Light');
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(2);
  });
});

describe('fireHaptics', () => {
  beforeEach(() => {
    clearDebounceState();
    jest.clearAllMocks();
  });

  it('should fire multiple intents', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptics([
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.JUDGMENT_LOCKED,
    ]);

    expect(Haptics.impactAsync).toHaveBeenCalledWith('Light');
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('Success');
  });

  it('should deduplicate intents', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptics([
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.CONFIRMATION_LIGHT,
      HapticIntent.CONFIRMATION_LIGHT,
    ], { force: true });

    // Should only fire once due to deduplication
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);
  });

  it('should respect enabled option', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptics(
      [HapticIntent.CONFIRMATION_LIGHT, HapticIntent.JUDGMENT_LOCKED],
      { enabled: false }
    );

    expect(Haptics.impactAsync).not.toHaveBeenCalled();
    expect(Haptics.notificationAsync).not.toHaveBeenCalled();
  });
});

describe('clearDebounceState', () => {
  it('should allow re-firing after clear', async () => {
    const Haptics = require('expo-haptics');

    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);

    // Second call should be debounced
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);

    // Clear and try again
    clearDebounceState();
    await fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(2);
  });
});
