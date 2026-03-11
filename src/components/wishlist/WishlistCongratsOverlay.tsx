/**
 * WishlistCongratsOverlay — Animated "Congrats!" celebration overlay.
 */
import React from 'react';
import { View, Text, Animated, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

interface WishlistCongratsOverlayProps {
  congratsScale: Animated.Value;
  congratsOpacity: Animated.Value;
}

export const WishlistCongratsOverlay = React.memo(function WishlistCongratsOverlay({
  congratsScale,
  congratsOpacity,
}: WishlistCongratsOverlayProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.congratsOverlay}>
      <Animated.View
        style={[
          styles.congratsContent,
          {
            backgroundColor: colors.card,
            transform: [{ scale: congratsScale }],
            opacity: congratsOpacity,
          },
        ]}
      >
        <View style={[styles.congratsIconWrap, { backgroundColor: colors.success + '20' }]}>
          <Ionicons name="trophy" size={48} color={colors.success} />
        </View>
        <Text style={[styles.congratsTitle, { color: colors.text }]}>Congrats!</Text>
        <Text style={[styles.congratsSubtitle, { color: colors.muted }]}>
          Added to your collection
        </Text>
      </Animated.View>
    </View>
  );
});

const styles = StyleSheet.create({
  congratsOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  congratsContent: {
    alignItems: 'center',
    padding: 32,
    borderRadius: 24,
    minWidth: 240,
  },
  congratsIconWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  congratsTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  congratsSubtitle: {
    fontSize: 14,
  },
});
