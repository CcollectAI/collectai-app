/**
 * AnimatedPressable
 * A Pressable with built-in scale animation on press.
 * Drop-in replacement for TouchableOpacity/Pressable.
 *
 * IMPLEMENTATION NOTE — why a single animated Pressable and not a wrapper:
 *
 * This used to render `<Pressable>` wrapping an inner `<Animated.View>` that
 * carried `style`. That broke the "drop-in replacement for Pressable" contract
 * this component documents: on a real Pressable, `style` lands on the element
 * the PARENT lays out. Here it landed one level in, so every layout-affecting
 * prop was silently dropped — the outer Pressable stayed unstyled and sized to
 * its content.
 *
 * The visible symptom was `flex: 1` doing nothing: buttons meant to split a row
 * evenly sized to their labels instead, so long labels overflowed and CTAs
 * stopped short of the screen edge. `margin`, `alignSelf`, `position` and
 * `width` were wrong in the same way. It was found four separate times in the
 * scan screens and "fixed" locally each time by wrapping the component in yet
 * another flex-owning View — treating the symptom.
 *
 * Animating the Pressable itself collapses the two boxes into one, so `style`
 * applies exactly where a Pressable's style would. `transform`/`opacity` still
 * run on the native driver.
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

// Created once at module scope — createAnimatedComponent() inside render would
// return a new component type every pass and remount the subtree on each render.
const AnimatedPressableBase = Animated.createAnimatedComponent(Pressable);

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
    <AnimatedPressableBase
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={disabled}
      style={[
        style,
        {
          transform: [{ scale: scaleAnim }],
          opacity: disabled ? 0.5 : 1,
        },
      ]}
      {...rest}
    >
      {children}
    </AnimatedPressableBase>
  );
}
