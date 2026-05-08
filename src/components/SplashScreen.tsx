/**
 * Branded splash screen with animated CollectAI logo.
 * Gradient background with pulsing glow ring and staggered dot indicators.
 */
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Image } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { fonts } from '@/theme/tokens';
import { DURATION } from '@/motion/tokens';

type Props = {
  onReady?: () => void;
};

export function SplashScreen({ onReady }: Props) {
  const { settings } = useSettings();
  const logoScale = useRef(new Animated.Value(0.3)).current;
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;
  const textTranslateY = useRef(new Animated.Value(12)).current;
  const subtitleOpacity = useRef(new Animated.Value(0)).current;
  const glowScale = useRef(new Animated.Value(1)).current;
  const dot0 = useRef(new Animated.Value(0.2)).current;
  const dot1 = useRef(new Animated.Value(0.2)).current;
  const dot2 = useRef(new Animated.Value(0.2)).current;

  useEffect(() => {
    // Pulsing glow ring
    const glowLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(glowScale, { toValue: 1.15, duration: DURATION.loop, useNativeDriver: true }),
        Animated.timing(glowScale, { toValue: 1.0, duration: DURATION.loop, useNativeDriver: true }),
      ]),
    );
    glowLoop.start();

    // Sequential dot pulse
    const dotAnims = [dot0, dot1, dot2];
    const dotLoop = Animated.loop(
      Animated.stagger(
        200,
        dotAnims.map((d) =>
          Animated.sequence([
            Animated.timing(d, { toValue: 1, duration: DURATION.slow, useNativeDriver: true }),
            Animated.timing(d, { toValue: 0.2, duration: DURATION.slow, useNativeDriver: true }),
          ]),
        ),
      ),
    );
    dotLoop.start();

    // Main entrance sequence
    Animated.sequence([
      Animated.parallel([
        Animated.spring(logoScale, {
          toValue: 1,
          friction: 6,
          tension: 40,
          useNativeDriver: true,
        }),
        Animated.timing(logoOpacity, {
          toValue: 1,
          duration: DURATION.slow,
          useNativeDriver: true,
        }),
      ]),
      Animated.parallel([
        Animated.timing(textOpacity, { toValue: 1, duration: DURATION.reveal, useNativeDriver: true }),
        Animated.timing(textTranslateY, { toValue: 0, duration: DURATION.reveal, useNativeDriver: true }),
      ]),
      Animated.timing(subtitleOpacity, {
        toValue: 1,
        duration: DURATION.reveal,
        useNativeDriver: true,
      }),
    ]).start(() => {
      if (onReady) {
        fireHaptic(HapticIntent.CONFIDENCE_HIGH, { enabled: settings.hapticsEnabled });
        setTimeout(onReady, 500);
      }
    });

    return () => {
      glowLoop.stop();
      dotLoop.stop();
    };
  }, []);

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={['#44A9A1', '#81D8D0', '#AEE6E1']}
        style={StyleSheet.absoluteFill}
      />

      {/* Glow ring behind logo */}
      <Animated.View
        style={[
          styles.glowRing,
          { opacity: logoOpacity, transform: [{ scale: glowScale }] },
        ]}
      />

      <Animated.View
        style={[
          styles.logoContainer,
          { opacity: logoOpacity, transform: [{ scale: logoScale }] },
        ]}
      >
        <View style={styles.logoCircle}>
          <Image
            source={require('../../assets/images/logo.png')}
            style={styles.logoImage}
            resizeMode="contain"
          />
        </View>
      </Animated.View>

      <Animated.Text
        style={[
          styles.appName,
          { opacity: textOpacity, transform: [{ translateY: textTranslateY }] },
        ]}
      >
        Sparrow Collect
      </Animated.Text>

      <Animated.Text style={[styles.subtitle, { opacity: subtitleOpacity }]}>
        Track. Value. Collect.
      </Animated.Text>

      <View style={styles.bottomDots}>
        {[dot0, dot1, dot2].map((d, i) => (
          <Animated.View key={i} style={[styles.dot, { opacity: d }]} />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  glowRing: {
    position: 'absolute',
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  logoContainer: {
    marginBottom: 24,
  },
  logoCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 10,
    overflow: 'hidden',
  },
  logoImage: {
    width: 100,
    height: 100,
  },
  appName: {
    fontSize: 36,
    fontFamily: fonts.black,
    color: '#FFFFFF',
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 16,
    fontFamily: fonts.medium,
    color: 'rgba(255,255,255,0.85)',
    marginTop: 8,
    letterSpacing: 2,
  },
  bottomDots: {
    position: 'absolute',
    bottom: 60,
    flexDirection: 'row',
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FFFFFF',
  },
});
