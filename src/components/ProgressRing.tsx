/**
 * ProgressRing Component
 * SVG-based circular progress indicator.
 */

import React, { useEffect, forwardRef, useImperativeHandle } from 'react';
import { View, StyleSheet } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import Animated from 'react-native-reanimated';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useProgressRing } from '@/hooks/useProgressRing';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export type ProgressRingProps = {
  /** Progress value (0-1) */
  progress: number;
  /** Size of the ring in pixels */
  size?: number;
  /** Stroke width */
  strokeWidth?: number;
  /** Track color (background circle) */
  trackColor?: string;
  /** Progress color (foreground circle) */
  progressColor?: string;
};

export type ProgressRingRef = {
  /** Set progress with animation */
  setProgress: (value: number) => void;
  /** Set progress instantly */
  setProgressInstant: (value: number) => void;
};

export const ProgressRing = forwardRef<ProgressRingRef, ProgressRingProps>(
  function ProgressRing(props, ref) {
    const {
      progress,
      size = 48,
      strokeWidth = 4,
      trackColor,
      progressColor,
    } = props;

    const { colors } = useAppTheme();
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;

    const { strokeDashoffset, setProgress, setProgressInstant } = useProgressRing(
      circumference,
      { initialProgress: progress }
    );

    // Expose methods via ref
    useImperativeHandle(ref, () => ({
      setProgress,
      setProgressInstant,
    }));

    // Update on progress prop change
    useEffect(() => {
      setProgress(progress);
    }, [progress, setProgress]);

    const track = trackColor ?? colors.border;
    const fill = progressColor ?? colors.accent;

    return (
      <View style={[styles.container, { width: size, height: size }]}>
        <Svg width={size} height={size}>
          {/* Background track */}
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={track}
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Progress arc */}
          <AnimatedCircle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={fill}
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            rotation={-90}
            origin={`${size / 2}, ${size / 2}`}
          />
        </Svg>
      </View>
    );
  }
);

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default ProgressRing;
