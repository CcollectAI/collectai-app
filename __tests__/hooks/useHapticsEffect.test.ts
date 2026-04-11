/**
 * Tests for useHapticsEffect and useConfidenceHaptic hooks.
 */

import { renderHook } from '@testing-library/react-native';

// Mock expo-haptics (same pattern as driver.test.ts)
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn().mockResolvedValue(undefined),
  notificationAsync: jest.fn().mockResolvedValue(undefined),
  ImpactFeedbackStyle: { Light: 'Light', Medium: 'Medium', Heavy: 'Heavy' },
  NotificationFeedbackType: { Success: 'Success', Warning: 'Warning', Error: 'Error' },
}));

// Mock settings
const mockSettings: Record<string, unknown> = { hapticsEnabled: true };
jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({ settings: mockSettings }),
}));

import { clearDebounceState } from '../../src/haptics';
import { HapticIntent } from '../../src/haptics';
import { useHapticsEffect, useConfidenceHaptic } from '../../src/hooks/useHapticsEffect';

// Get the mocked expo-haptics to verify calls
const Haptics = require('expo-haptics');

describe('useHapticsEffect', () => {
  beforeEach(() => {
    clearDebounceState();
    jest.clearAllMocks();
    mockSettings.hapticsEnabled = true;
  });

  it('should not fire on first render', () => {
    renderHook(() =>
      useHapticsEffect({
        intents: [HapticIntent.CONFIRMATION_LIGHT],
        stableKey: 'initial',
      })
    );

    expect(Haptics.impactAsync).not.toHaveBeenCalled();
    expect(Haptics.notificationAsync).not.toHaveBeenCalled();
  });

  it('should fire when stableKey changes', () => {
    const { rerender } = renderHook(
      ({ stableKey }) =>
        useHapticsEffect({
          intents: [HapticIntent.JUDGMENT_LOCKED],
          stableKey,
        }),
      { initialProps: { stableKey: 'a' as string | number } }
    );

    expect(Haptics.notificationAsync).not.toHaveBeenCalled();

    rerender({ stableKey: 'b' });
    // JUDGMENT_LOCKED fires notificationAsync(Success)
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('Success');
  });

  it('should not fire when stableKey stays the same', () => {
    const { rerender } = renderHook(
      ({ stableKey }) =>
        useHapticsEffect({
          intents: [HapticIntent.CONFIRMATION_LIGHT],
          stableKey,
        }),
      { initialProps: { stableKey: 'same' as string } }
    );

    rerender({ stableKey: 'same' });
    rerender({ stableKey: 'same' });

    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('should not fire when skip is true', () => {
    const { rerender } = renderHook(
      ({ stableKey, skip }) =>
        useHapticsEffect({
          intents: [HapticIntent.CONFIRMATION_LIGHT],
          stableKey,
          skip,
        }),
      { initialProps: { stableKey: 'a' as string, skip: true } }
    );

    rerender({ stableKey: 'b', skip: true });
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('should not fire when hapticsEnabled is false', () => {
    mockSettings.hapticsEnabled = false;

    const { rerender } = renderHook(
      ({ stableKey }) =>
        useHapticsEffect({
          intents: [HapticIntent.CONFIRMATION_LIGHT],
          stableKey,
        }),
      { initialProps: { stableKey: 'a' as string } }
    );

    rerender({ stableKey: 'b' });
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('should fire for CONFIRMATION_LIGHT intent', () => {
    const { rerender } = renderHook(
      ({ stableKey }) =>
        useHapticsEffect({
          intents: [HapticIntent.CONFIRMATION_LIGHT],
          stableKey,
        }),
      { initialProps: { stableKey: 'a' as string } }
    );

    rerender({ stableKey: 'b' });
    // CONFIRMATION_LIGHT fires impactAsync(Light)
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Light');
  });
});

describe('useConfidenceHaptic', () => {
  beforeEach(() => {
    clearDebounceState();
    jest.clearAllMocks();
    mockSettings.hapticsEnabled = true;
  });

  it('should not fire on first render', () => {
    renderHook(() => useConfidenceHaptic(0.9, 'scan-1'));
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
    expect(Haptics.notificationAsync).not.toHaveBeenCalled();
  });

  it('should fire for high confidence', () => {
    const { rerender } = renderHook(
      ({ confidence, key }) => useConfidenceHaptic(confidence, key),
      { initialProps: { confidence: 0.9 as number | null, key: 'a' as string } }
    );

    rerender({ confidence: 0.95, key: 'b' });
    // CONFIDENCE_HIGH fires impactAsync(Medium) then impactAsync(Light)
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Medium');
  });

  it('should fire for low confidence', () => {
    const { rerender } = renderHook(
      ({ confidence, key }) => useConfidenceHaptic(confidence, key),
      { initialProps: { confidence: 0.3 as number | null, key: 'a' as string } }
    );

    rerender({ confidence: 0.2, key: 'b' });
    // UNCERTAINTY_PRESENT fires impactAsync(Light)
    expect(Haptics.impactAsync).toHaveBeenCalledWith('Light');
  });

  it('should not fire when confidence is null', () => {
    const { rerender } = renderHook(
      ({ confidence, key }) => useConfidenceHaptic(confidence, key),
      { initialProps: { confidence: null as number | null, key: 'a' as string } }
    );

    rerender({ confidence: null, key: 'b' });
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('should respect skip option', () => {
    const { rerender } = renderHook(
      ({ confidence, key }) => useConfidenceHaptic(confidence, key, { skip: true }),
      { initialProps: { confidence: 0.9 as number | null, key: 'a' as string } }
    );

    rerender({ confidence: 0.95, key: 'b' });
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });
});
