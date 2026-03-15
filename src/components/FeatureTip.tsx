/**
 * FeatureTip — tooltip overlay for in-app feature guidance.
 *
 * Shows a Tiffany Blue tooltip with a triangle pointer,
 * "Got it" dismiss button, and fades in on mount.
 * Each tip appears once per user (persisted via FeatureTourProvider).
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, Pressable, Animated, StyleSheet } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';
import { useFeatureTour, type TipId } from '@/lib/featureTour';
import { BRAND_COLORS } from '@/constants/colors';

type FeatureTipProps = {
  /** Unique identifier for this tip */
  tipId: TipId;
  /** Tooltip message text */
  message: string;
  /** Position of the triangle pointer */
  pointerPosition?: 'top' | 'bottom';
  /** Optional style overrides for positioning */
  style?: StyleProp<ViewStyle>;
};

export function FeatureTip({ tipId, message, pointerPosition = 'top', style }: FeatureTipProps) {
  const { isDismissed, dismiss, ready } = useFeatureTour();
  const fadeAnim = useRef(new Animated.Value(0)).current;

  const visible = ready && !isDismissed(tipId);

  useEffect(() => {
    if (!visible) return;
    const anim = Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [visible, fadeAnim]);

  if (!visible) return null;

  return (
    <Animated.View
      style={[styles.container, { opacity: fadeAnim }, style]}
      accessibilityRole="alert"
      accessibilityLabel={message}
    >
      {pointerPosition === 'top' && <View style={styles.pointerTop} />}
      <View style={styles.bubble}>
        <Text style={styles.message}>{message}</Text>
        <Pressable
          onPress={() => dismiss(tipId)}
          style={styles.dismissBtn}
          accessibilityRole="button"
          accessibilityLabel="Dismiss tip"
        >
          <Text style={styles.dismissText}>Got it</Text>
        </Pressable>
      </View>
      {pointerPosition === 'bottom' && <View style={styles.pointerBottom} />}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    zIndex: 1000,
    alignItems: 'center',
    maxWidth: 280,
  },
  bubble: {
    backgroundColor: BRAND_COLORS.tiffany,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    flexDirection: 'column',
    gap: 8,
  },
  message: {
    color: '#0F172A',
    fontSize: 14,
    lineHeight: 20,
    fontFamily: 'Roboto_400Regular',
  },
  dismissBtn: {
    alignSelf: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 4,
    backgroundColor: 'rgba(0,0,0,0.15)',
    borderRadius: 8,
  },
  dismissText: {
    color: '#0F172A',
    fontSize: 13,
    fontWeight: '600',
    fontFamily: 'Roboto_500Medium',
  },
  pointerTop: {
    width: 0,
    height: 0,
    borderLeftWidth: 8,
    borderRightWidth: 8,
    borderBottomWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: BRAND_COLORS.tiffany,
    marginBottom: -1,
  },
  pointerBottom: {
    width: 0,
    height: 0,
    borderLeftWidth: 8,
    borderRightWidth: 8,
    borderTopWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderTopColor: BRAND_COLORS.tiffany,
    marginTop: -1,
  },
});
