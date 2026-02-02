/**
 * SwipeableRow - Provides swipe-to-delete/action functionality.
 * Swipe left to reveal action button (delete by default).
 */

import React, { useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  PanResponder,
  Pressable,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import haptics from '@/lib/haptics';

interface Props {
  children: React.ReactNode;
  onDelete?: () => void;
  onAction?: () => void;
  actionIcon?: keyof typeof Ionicons.glyphMap;
  actionLabel?: string;
  actionColor?: string;
  deleteLabel?: string;
  disabled?: boolean;
}

const SWIPE_THRESHOLD = 80;
const ACTION_WIDTH = 80;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

export function SwipeableRow({
  children,
  onDelete,
  onAction,
  actionIcon = 'trash-outline',
  actionLabel = 'Delete',
  actionColor = '#ef4444',
  deleteLabel,
  disabled = false,
}: Props) {
  const translateX = useRef(new Animated.Value(0)).current;
  const isOpen = useRef(false);

  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gestureState) => {
        if (disabled) return false;
        return Math.abs(gestureState.dx) > 10 && Math.abs(gestureState.dy) < 10;
      },
      onPanResponderGrant: () => {
        haptics.lightTap();
      },
      onPanResponderMove: (_, gestureState) => {
        // Only allow swiping left (negative dx)
        if (gestureState.dx < 0) {
          translateX.setValue(Math.max(gestureState.dx, -ACTION_WIDTH * 1.5));
        } else if (isOpen.current) {
          translateX.setValue(Math.min(gestureState.dx - ACTION_WIDTH, 0));
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        const shouldOpen = gestureState.dx < -SWIPE_THRESHOLD;
        const shouldClose = gestureState.dx > SWIPE_THRESHOLD / 2;

        if (shouldOpen && !isOpen.current) {
          Animated.spring(translateX, {
            toValue: -ACTION_WIDTH,
            useNativeDriver: true,
            tension: 100,
            friction: 10,
          }).start();
          isOpen.current = true;
          haptics.mediumTap();
        } else if (shouldClose || !shouldOpen) {
          Animated.spring(translateX, {
            toValue: 0,
            useNativeDriver: true,
            tension: 100,
            friction: 10,
          }).start();
          isOpen.current = false;
        }
      },
    })
  ).current;

  const handleAction = () => {
    haptics.warning();
    // Animate close first, then call action
    Animated.timing(translateX, {
      toValue: 0,
      duration: 200,
      useNativeDriver: true,
    }).start(() => {
      isOpen.current = false;
      if (onAction) {
        onAction();
      } else if (onDelete) {
        onDelete();
      }
    });
  };

  const close = () => {
    Animated.spring(translateX, {
      toValue: 0,
      useNativeDriver: true,
    }).start();
    isOpen.current = false;
  };

  return (
    <View style={styles.container}>
      {/* Action button (behind the row) */}
      <View style={[styles.actionContainer, { backgroundColor: actionColor }]}>
        <Pressable style={styles.actionButton} onPress={handleAction}>
          <Ionicons name={actionIcon} size={22} color="#fff" />
          <Text style={styles.actionText}>{deleteLabel || actionLabel}</Text>
        </Pressable>
      </View>

      {/* Swipeable content */}
      <Animated.View
        style={[styles.content, { transform: [{ translateX }] }]}
        {...panResponder.panHandlers}
      >
        {children}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
  },
  actionContainer: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    width: ACTION_WIDTH,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionButton: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    width: '100%',
  },
  actionText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 4,
  },
  content: {
    backgroundColor: '#fff',
  },
});

export default SwipeableRow;
