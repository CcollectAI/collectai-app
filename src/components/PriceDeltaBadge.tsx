/**
 * PriceDeltaBadge - Shows price change with color and animation.
 * Includes pulse animation for significant changes.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  delta: number; // Percentage change (e.g., 5.2 for +5.2%)
  showAnimation?: boolean;
  size?: 'small' | 'medium' | 'large';
  showIcon?: boolean;
}

export function PriceDeltaBadge({
  delta,
  showAnimation = true,
  size = 'medium',
  showIcon = true,
}: Props) {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const isPositive = delta >= 0;
  const isSignificant = Math.abs(delta) >= 5;

  useEffect(() => {
    if (showAnimation && isSignificant) {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.1,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 500,
            useNativeDriver: true,
          }),
        ])
      );
      animation.start();
      return () => animation.stop();
    }
  }, [showAnimation, isSignificant, pulseAnim]);

  const backgroundColor = isPositive ? '#22c55e' : '#ef4444';
  const iconName = isPositive ? 'trending-up' : 'trending-down';

  const fontSize = size === 'small' ? 11 : size === 'large' ? 15 : 13;
  const iconSize = size === 'small' ? 12 : size === 'large' ? 18 : 14;
  const paddingH = size === 'small' ? 6 : size === 'large' ? 12 : 8;
  const paddingV = size === 'small' ? 2 : size === 'large' ? 6 : 4;

  return (
    <Animated.View
      style={[
        styles.badge,
        {
          backgroundColor: backgroundColor + '20',
          paddingHorizontal: paddingH,
          paddingVertical: paddingV,
          transform: [{ scale: pulseAnim }],
        },
      ]}
    >
      {showIcon && (
        <Ionicons
          name={iconName}
          size={iconSize}
          color={backgroundColor}
          style={{ marginRight: 4 }}
        />
      )}
      <Text style={[styles.text, { color: backgroundColor, fontSize }]}>
        {isPositive ? '+' : ''}{delta.toFixed(1)}%
      </Text>
    </Animated.View>
  );
}

/**
 * HotBadge - Shows "Hot" indicator for trending items.
 */
export function HotBadge({ size = 'medium' }: { size?: 'small' | 'medium' | 'large' }) {
  const flameAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(flameAnim, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(flameAnim, {
          toValue: 0,
          duration: 600,
          useNativeDriver: true,
        }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, [flameAnim]);

  const scale = flameAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.15],
  });

  const fontSize = size === 'small' ? 10 : size === 'large' ? 14 : 12;
  const iconSize = size === 'small' ? 12 : size === 'large' ? 18 : 14;
  const paddingH = size === 'small' ? 6 : size === 'large' ? 12 : 8;
  const paddingV = size === 'small' ? 2 : size === 'large' ? 5 : 3;

  return (
    <Animated.View
      style={[
        styles.hotBadge,
        {
          paddingHorizontal: paddingH,
          paddingVertical: paddingV,
          transform: [{ scale }],
        },
      ]}
    >
      <Ionicons name="flame" size={iconSize} color="#fff" />
      <Text style={[styles.hotText, { fontSize }]}>HOT</Text>
    </Animated.View>
  );
}

/**
 * PriceChangeIndicator - Simple up/down arrow with color.
 */
export function PriceChangeIndicator({
  delta,
  colors,
}: {
  delta: number;
  colors: { text: string; muted: string };
}) {
  if (delta === 0) {
    return (
      <Text style={[styles.changeText, { color: colors.muted }]}>—</Text>
    );
  }

  const isPositive = delta > 0;
  const color = isPositive ? '#22c55e' : '#ef4444';

  return (
    <View style={styles.changeIndicator}>
      <Ionicons
        name={isPositive ? 'caret-up' : 'caret-down'}
        size={12}
        color={color}
      />
      <Text style={[styles.changeText, { color }]}>
        {Math.abs(delta).toFixed(1)}%
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
  },
  text: {
    fontWeight: '600',
  },
  hotBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f97316',
    borderRadius: 12,
    gap: 2,
  },
  hotText: {
    color: '#fff',
    fontWeight: '700',
  },
  changeIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  changeText: {
    fontSize: 12,
    fontWeight: '500',
  },
});

export default PriceDeltaBadge;
