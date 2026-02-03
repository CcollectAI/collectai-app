/**
 * ConfettiBurst Component
 * Renders confetti particles for celebration moments.
 */

import React, { forwardRef, useImperativeHandle } from 'react';
import { View, Animated, StyleSheet } from 'react-native';
import { useConfetti, UseConfettiOptions } from '@/hooks/useConfetti';

export type ConfettiBurstProps = UseConfettiOptions & {
  /** Style for the container */
  style?: any;
};

export type ConfettiBurstRef = {
  /** Trigger a confetti burst */
  burst: () => void;
  /** Whether animation is currently playing */
  isAnimating: boolean;
};

export const ConfettiBurst = forwardRef<ConfettiBurstRef, ConfettiBurstProps>(
  function ConfettiBurst(props, ref) {
    const { style, ...confettiOptions } = props;
    const { particles, burst, getParticleStyle, isAnimating } = useConfetti(confettiOptions);

    // Expose methods via ref
    useImperativeHandle(ref, () => ({
      burst,
      isAnimating,
    }));

    if (particles.length === 0) {
      return null;
    }

    return (
      <View style={[styles.container, style]} pointerEvents="none">
        {particles.map((particle) => (
          <Animated.View
            key={particle.id}
            style={getParticleStyle(particle)}
          />
        ))}
      </View>
    );
  }
);

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'visible',
  },
});

export default ConfettiBurst;
