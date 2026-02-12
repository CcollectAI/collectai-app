/**
 * AnimatedCounter
 * Smoothly animates between numeric values using spring physics.
 *
 * Usage:
 *   <AnimatedCounter value={12345.67} format={(v) => `${v.toFixed(2)}`} />
 */

import React, { useEffect, useRef } from 'react';
import { Animated, TextStyle, StyleProp, Text } from 'react-native';
import { DURATION } from './tokens';

export interface AnimatedCounterProps {
  /** Target numeric value */
  value: number;
  /** Format function for display. Default: Math.round */
  format?: (value: number) => string;
  /** Text style */
  style?: StyleProp<TextStyle>;
  /** Animation duration in ms. Default: DURATION.slow (400) */
  duration?: number;
  /** Whether animation is enabled. Default: true */
  enabled?: boolean;
  /** Accessibility label override */
  accessibilityLabel?: string;
}

export function AnimatedCounter({
  value,
  format = (v) => Math.round(v).toLocaleString(),
  style,
  duration = DURATION.slow,
  enabled = true,
  accessibilityLabel,
}: AnimatedCounterProps) {
  const animatedValue = useRef(new Animated.Value(value)).current;
  const displayRef = useRef<Text>(null);
  const currentFormat = useRef(format);
  currentFormat.current = format;

  // Keep a ref to the latest listener ID so we can remove it
  const listenerRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      animatedValue.setValue(value);
      return;
    }

    Animated.timing(animatedValue, {
      toValue: value,
      duration,
      useNativeDriver: false, // need JS-side interpolation for text
    }).start();
  }, [value, duration, enabled, animatedValue]);

  // Listen to animated value changes and update the text
  useEffect(() => {
    const id = animatedValue.addListener(({ value: v }) => {
      if (displayRef.current) {
        displayRef.current.setNativeProps({
          text: currentFormat.current(v),
        });
      }
    });
    listenerRef.current = id;

    return () => {
      animatedValue.removeListener(id);
    };
  }, [animatedValue]);

  // For the text display, we use a simple Text that gets updated
  // via setNativeProps for performance (no re-renders during animation)
  return (
    <AnimatedText
      ref={displayRef}
      value={animatedValue}
      format={format}
      style={style}
      accessibilityLabel={accessibilityLabel ?? format(value)}
    />
  );
}

// Inner component that renders the animated text
interface AnimatedTextProps {
  value: Animated.Value;
  format: (v: number) => string;
  style?: StyleProp<TextStyle>;
  accessibilityLabel?: string;
}

const AnimatedText = React.forwardRef<Text, AnimatedTextProps>(
  function AnimatedText({ value, format, style, accessibilityLabel }, _ref) {
    const [displayText, setDisplayText] = React.useState('');

    useEffect(() => {
      const id = value.addListener(({ value: v }) => {
        setDisplayText(format(v));
      });
      // Set initial value
      // @ts-expect-error - accessing internal _value for initial render
      setDisplayText(format(value._value ?? 0));
      return () => value.removeListener(id);
    }, [value, format]);

    return (
      <Text
        style={style}
        accessibilityLabel={accessibilityLabel}
        accessibilityRole="text"
      >
        {displayText}
      </Text>
    );
  },
);
