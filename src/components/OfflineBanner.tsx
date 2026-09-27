/**
 * OfflineBanner — a pill just above the bottom bar, shown while offline.
 * Also displays the number of queued mutations waiting to be replayed.
 *
 * WHERE, and why (2026-09-27, OPEN_DECISIONS #10): it used to slide down over
 * the TOP of every screen and covered the header — title, back, bell, inbox,
 * settings — for as long as the device was offline. A pill above the bottom
 * bar hides no control, changes no screen's layout, and keeps clear of toasts,
 * which enter from the top. Not a status-bar strip: on iPhones with a Dynamic
 * Island the middle of that strip is taken.
 *
 * Wire into app/_layout.tsx alongside the ToastProvider.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useAppTheme } from '@/hooks/useAppTheme';
import { getQueueLength } from '@/lib/mutationQueue';
import { EXTERNAL_TAB_BAR_HEIGHT } from '@/components/ExternalTabBar';
import { useTranslation } from 'react-i18next';

/**
 * Bottom offset that clears the bottom bar. ExternalTabBar (tab screens) and
 * QuickNavBar (the rest) are both `58 + max(insets.bottom, 10)` tall; screens
 * with neither (auth, camera) get the pill a little higher, which is harmless.
 */
export function offlinePillBottom(insetsBottom: number): number {
  return EXTERNAL_TAB_BAR_HEIGHT + Math.max(insetsBottom, 10) + 8;
}

export function OfflineBanner() {
  const { isOnline } = useNetworkStatus();
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  // Starts hidden below the screen edge; springs up into place when offline.
  const translateY = useRef(new Animated.Value(300)).current;
  const [queueCount, setQueueCount] = useState(0);

  const bottom = offlinePillBottom(insets.bottom);
  // Far enough down to be fully off-screen, whatever the bar height.
  const hiddenY = bottom + 80;

  useEffect(() => {
    setQueueCount(getQueueLength());

    if (!isOnline) {
      const interval = setInterval(() => {
        setQueueCount(getQueueLength());
      }, 2_000);
      return () => clearInterval(interval);
    }
  }, [isOnline]);

  useEffect(() => {
    Animated.spring(translateY, {
      toValue: isOnline ? hiddenY : 0,
      useNativeDriver: true,
      damping: 20,
      stiffness: 200,
    }).start();
  }, [isOnline, hiddenY, translateY]);

  const label =
    queueCount === 0
      ? t('offline.banner')
      : t(queueCount === 1 ? 'offline.banner_queued_one' : 'offline.banner_queued_many', { count: queueCount });

  return (
    <Animated.View
      accessibilityRole="alert"
      accessibilityLabel={isOnline ? undefined : `${label}. ${t('offline.banner_a11y_cached')}`}
      accessibilityLiveRegion="polite"
      style={[
        styles.container,
        {
          bottom,
          backgroundColor: colors.offlineBanner,
          transform: [{ translateY }],
          // pointerEvents in style (RN 0.81+) — legacy prop on
          // Animated.View can be silently ignored, blocking taps to the
          // top of every screen while offline.
          pointerEvents: 'none',
        },
      ]}
    >
      <Ionicons name="cloud-offline-outline" size={16} color={colors.offlineBannerText} />
      <Text style={[styles.text, { color: colors.offlineBannerText }]}>
        {label}
      </Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 999,
    zIndex: 9998,
    gap: 8,
    // Lifted off the content it floats over.
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  text: {
    fontSize: 13,
    fontWeight: '600',
  },
});
