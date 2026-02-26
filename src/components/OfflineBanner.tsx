/**
 * OfflineBanner — slide-down banner shown when the device is offline.
 * Also displays the number of queued mutations waiting to be replayed.
 *
 * Wire into app/_layout.tsx alongside the ToastProvider.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useAppTheme } from '@/hooks/useAppTheme';
import { getQueueLength } from '@/lib/mutationQueue';

export function OfflineBanner() {
  const { isOnline } = useNetworkStatus();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const translateY = useRef(new Animated.Value(-60)).current;
  const [queueCount, setQueueCount] = useState(0);

  // Re-read the queue length whenever the online status changes (or periodically)
  useEffect(() => {
    setQueueCount(getQueueLength());

    if (!isOnline) {
      // Poll queue length while offline so the count stays fresh
      const interval = setInterval(() => {
        setQueueCount(getQueueLength());
      }, 2_000);
      return () => clearInterval(interval);
    }
  }, [isOnline]);

  useEffect(() => {
    Animated.spring(translateY, {
      toValue: isOnline ? -60 : 0,
      useNativeDriver: true,
      damping: 20,
      stiffness: 200,
    }).start();
  }, [isOnline, translateY]);

  const queueSuffix =
    queueCount > 0
      ? ` \u2014 ${queueCount} change${queueCount > 1 ? 's' : ''} queued`
      : '';

  return (
    <Animated.View
      pointerEvents="none"
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
          top: insets.top + (Platform.OS === 'android' ? 0 : 0),
          backgroundColor: colors.offlineBanner,
          transform: [{ translateY }],
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
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    zIndex: 9998,
    gap: 8,
  },
  text: {
    fontSize: 13,
    fontWeight: '600',
  },
});
