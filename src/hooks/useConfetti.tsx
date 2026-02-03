/**
 * useConfetti Hook
 * Particle burst animation for celebration moments.
 */

import { useState, useCallback, useRef, useMemo } from 'react';
import { Animated, ViewStyle } from 'react-native';
import { useReduceMotion } from '../lib/accessibility';

export type Particle = {
  id: number;
  x: Animated.Value;
  y: Animated.Value;
  scale: Animated.Value;
  opacity: Animated.Value;
  rotation: Animated.Value;
  color: string;
};

export type UseConfettiOptions = {
  /** Number of particles */
  particleCount?: number;
  /** Animation duration in ms */
  duration?: number;
  /** Colors to use for particles */
  colors?: string[];
  /** Spread radius */
  spread?: number;
};

export type UseConfettiReturn = {
  /** Current particles */
  particles: Particle[];
  /** Trigger a confetti burst */
  burst: () => void;
  /** Get animated style for a particle */
  getParticleStyle: (particle: Particle) => Animated.WithAnimatedObject<ViewStyle>;
  /** Whether animation is currently playing */
  isAnimating: boolean;
};

const DEFAULT_COLORS = ['#1fb6ff', '#38bdf8', '#0BA86C', '#FFD700', '#FF6B6B'];

/**
 * Hook for confetti particle burst animation.
 */
export function useConfetti(options: UseConfettiOptions = {}): UseConfettiReturn {
  const {
    particleCount = 12,
    duration = 600,
    colors = DEFAULT_COLORS,
    spread = 80,
  } = options;

  const reduceMotion = useReduceMotion();
  const [particles, setParticles] = useState<Particle[]>([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const idCounter = useRef(0);

  const createParticles = useCallback((): Particle[] => {
    return Array.from({ length: particleCount }, (_, i) => {
      const angle = (i / particleCount) * Math.PI * 2;
      const color = colors[i % colors.length];

      return {
        id: idCounter.current++,
        x: new Animated.Value(0),
        y: new Animated.Value(0),
        scale: new Animated.Value(1),
        opacity: new Animated.Value(1),
        rotation: new Animated.Value(0),
        color,
      };
    });
  }, [particleCount, colors]);

  const burst = useCallback(() => {
    if (reduceMotion || isAnimating) return;

    const newParticles = createParticles();
    setParticles(newParticles);
    setIsAnimating(true);

    const animations = newParticles.map((particle, i) => {
      const angle = (i / particleCount) * Math.PI * 2;
      const distance = spread * (0.5 + Math.random() * 0.5);
      const targetX = Math.cos(angle) * distance;
      const targetY = Math.sin(angle) * distance - 20; // Slight upward bias

      return Animated.parallel([
        Animated.timing(particle.x, {
          toValue: targetX,
          duration,
          useNativeDriver: true,
        }),
        Animated.timing(particle.y, {
          toValue: targetY,
          duration,
          useNativeDriver: true,
        }),
        Animated.timing(particle.scale, {
          toValue: 0,
          duration,
          useNativeDriver: true,
        }),
        Animated.timing(particle.opacity, {
          toValue: 0,
          duration,
          useNativeDriver: true,
        }),
        Animated.timing(particle.rotation, {
          toValue: Math.random() * 4 - 2, // Random rotation
          duration,
          useNativeDriver: true,
        }),
      ]);
    });

    Animated.parallel(animations).start(() => {
      setParticles([]);
      setIsAnimating(false);
    });
  }, [reduceMotion, isAnimating, createParticles, particleCount, spread, duration]);

  const getParticleStyle = useCallback(
    (particle: Particle): Animated.WithAnimatedObject<ViewStyle> => ({
      position: 'absolute',
      width: 8,
      height: 8,
      borderRadius: 4,
      backgroundColor: particle.color,
      transform: [
        { translateX: particle.x },
        { translateY: particle.y },
        { scale: particle.scale },
        {
          rotate: particle.rotation.interpolate({
            inputRange: [-2, 2],
            outputRange: ['-360deg', '360deg'],
          }),
        },
      ],
      opacity: particle.opacity,
    }),
    []
  );

  return {
    particles,
    burst,
    getParticleStyle,
    isAnimating,
  };
}
