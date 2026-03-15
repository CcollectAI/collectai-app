/**
 * Accessibility Context
 * Provides app-wide accessibility settings and hooks.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { AccessibilityInfo } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

export type AccessibilitySettings = {
  /** High contrast mode enabled */
  highContrastEnabled: boolean;
  /** Reduce motion (user preference, separate from OS) */
  reduceMotionEnabled: boolean;
  /** Large text mode */
  largeTextEnabled: boolean;
};

const DEFAULTS: AccessibilitySettings = {
  highContrastEnabled: false,
  reduceMotionEnabled: false,
  largeTextEnabled: false,
};

type AccessibilityContextType = {
  settings: AccessibilitySettings;
  updateSettings: (patch: Partial<AccessibilitySettings>) => void;
  /** OS-level reduce motion preference */
  systemReduceMotion: boolean;
  /** Combined check: user OR system reduce motion */
  shouldReduceMotion: boolean;
  ready: boolean;
};

const AccessibilityCtx = createContext<AccessibilityContextType>({
  settings: DEFAULTS,
  updateSettings: () => {},
  systemReduceMotion: false,
  shouldReduceMotion: false,
  ready: false,
});

const STORAGE_KEY = '@accessibility_settings';

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AccessibilitySettings>(DEFAULTS);
  const [systemReduceMotion, setSystemReduceMotion] = useState(false);
  const [ready, setReady] = useState(false);

  // Load saved settings
  useEffect(() => {
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(STORAGE_KEY);
        if (stored) {
          setSettings({ ...DEFAULTS, ...JSON.parse(stored) });
        }
      } catch (e) {
        logger.debug('[a11y] Failed to load accessibility settings:', e);
      }
      setReady(true);
    })();
  }, []);

  // Listen to OS reduce motion setting
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setSystemReduceMotion);

    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setSystemReduceMotion
    );

    return () => subscription.remove();
  }, []);

  const updateSettings = useCallback((patch: Partial<AccessibilitySettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch((e) => {
        logger.debug('[a11y] Failed to persist accessibility settings:', e);
      });
      return next;
    });
  }, []);

  const shouldReduceMotion = settings.reduceMotionEnabled || systemReduceMotion;

  const value = useMemo(
    () => ({
      settings,
      updateSettings,
      systemReduceMotion,
      shouldReduceMotion,
      ready,
    }),
    [settings, updateSettings, systemReduceMotion, shouldReduceMotion, ready]
  );

  return (
    <AccessibilityCtx.Provider value={value}>
      {children}
    </AccessibilityCtx.Provider>
  );
}

export function useAccessibility() {
  return useContext(AccessibilityCtx);
}

/**
 * Hook to check if reduce motion should be applied.
 * Respects both user setting and OS setting.
 */
export function useShouldReduceMotion(): boolean {
  const { shouldReduceMotion } = useAccessibility();
  return shouldReduceMotion;
}

/**
 * Hook to check if high contrast mode is enabled.
 */
export function useHighContrast(): boolean {
  const { settings } = useAccessibility();
  return settings.highContrastEnabled;
}
