/**
 * OfflineBanner — slide-down banner shown when the device is offline.
 * Also displays the number of queued mutations waiting to be replayed.
 *
 * Wire into app/_layout.tsx alongside the ToastProvider.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text, Platform, StatusBar } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useAppTheme } from '@/hooks/useAppTheme';
import { getQueueLength } from '@/lib/mutationQueue';

// Visible banner content height (icon + text + vertical padding). The full
// rendered height is this value + the safe-area top inset (status bar / notch).
const BANNER_BODY_HEIGHT = 36;

export function OfflineBanner() {
  const { isOnline } = useNetworkStatus();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  // Start fully off-screen \u2014 actual hidden offset is computed below once insets resolve.
  const translateY = useRef(new Animated.Value(-200)).current;
  const [queueCount, setQueueCount] = useState(0);

  const topInset =
    insets.top || (Platform.OS === 'ios' ? 47 : StatusBar.currentHeight ?? 24);
  // Pull the banner fully above the screen edge, including the status-bar area
  // it paints over when shown. The +12 is a small over-slide so the bottom edge
  // doesn't peek past the notch during the spring overshoot.
  const hiddenY = -(topInset + BANNER_BODY_HEIGHT + 12);

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

  const queueSuffix =
    queueCount > 0
      ? ` \u2014 ${queueCount} change${queueCount > 1 ? 's' : ''} queued`
      : '';

  return (
    <Animated.View
      accessibilityRole="alert"
      accessibilityLabel={
        isOnline
          ? undefined
          : `You are offline. Showing cached data.${queueCount > 0 ? ` ${queueCount} changes queued.` : ''}`
      }
      accessibilityLiveRegion="polite"
      style={[
        styles.container,
        {
          paddingTop: topInset + 8,
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
        You're offline{queueSuffix}
      </Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingBottom: 8,
    paddingHorizontal: 16,
    zIndex: 9998,
    gap: 8,
  },
  text: {
    fontSize: 13,
    fontWeight: '600',
  },
});
