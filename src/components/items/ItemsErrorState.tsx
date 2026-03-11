/**
 * ItemsErrorState — Error screen with retry button.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface ItemsErrorStateProps {
  error: string;
  onRetry: () => void;
}

export const ItemsErrorState = React.memo(function ItemsErrorState({
  error,
  onRetry,
}: ItemsErrorStateProps) {
  const { colors } = useAppTheme();

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <View style={styles.centerContainer}>
        <Ionicons name="alert-circle-outline" size={48} color="#B42318" />
        <Text style={[styles.errorText, { color: "#B42318" }]}>{error}</Text>
        <AnimatedPressable
          style={[styles.retryBtn, { backgroundColor: colors.accent }]}
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel="Retry loading items"
        >
          <Text style={styles.retryText}>Retry</Text>
        </AnimatedPressable>
      </View>
    </SafeAreaView>
  );
});

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  errorText: {
    marginTop: 12,
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  retryBtn: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 6,
  },
  retryText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
});
