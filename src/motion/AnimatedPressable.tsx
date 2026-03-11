/**
 * AnimatedPressable
 * A Pressable with built-in scale animation on press.
 * Drop-in replacement for TouchableOpacity/Pressable.
 */

import React, { useRef, useCallback } from 'react';
import {
  Animated,
  GestureResponderEvent,
  Pressable,
  PressableProps,
  ViewStyle,
  StyleProp,
} from 'react-native';
import { SCALE, SPRING } from './tokens';

export interface AnimatedPressableProps extends Omit<PressableProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  scaleValue?: number;
  children?: React.ReactNode;
}

export function AnimatedPressable({
  style,
  scaleValue = SCALE.pressed,
  onPressIn,
  onPressOut,
  children,
  disabled,
  ...rest
}: AnimatedPressableProps) {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = useCallback(
    (e: GestureResponderEvent) => {
      Animated.spring(scaleAnim, {
        toValue: scaleValue,
        tension: SPRING.tension,
        friction: SPRING.friction,
        useNativeDriver: true,
      }).start();
      onPressIn?.(e);
    },
    [scaleAnim, scaleValue, onPressIn]
  );

  const handlePressOut = useCallback(
    (e: GestureResponderEvent) => {
      Animated.spring(scaleAnim, {
        toValue: 1,
        tension: SPRING.tension,
        friction: SPRING.friction,
        useNativeDriver: true,
      }).start();
      onPressOut?.(e);
    },
    [scaleAnim, onPressOut]
  );

  return (
    <Pressable
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={disabled}
      {...rest}
    >
      <Animated.View
        style={[
          style,
          {
            transform: [{ scale: scaleAnim }],
            opacity: disabled ? 0.5 : 1,
          },
        ]}
      >
        {children}
      </Animated.View>
    </Pressable>
  );
}
