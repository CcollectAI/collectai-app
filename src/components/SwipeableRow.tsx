/**
 * SwipeableRow - Provides swipe-to-reveal action functionality.
 * Swipe left/right to reveal action buttons (watchlist, share, delete, etc.).
 * Includes long-press support for accessibility.
 */

import React, { useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  PanResponder,
  Pressable,
  Dimensions,
  GestureResponderEvent,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';

/** Swipe action configuration */
export type SwipeAction = {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  onPress: () => void;
};

interface Props {
  children: React.ReactNode;
  /** Legacy: single delete action */
  onDelete?: () => void;
  /** Legacy: single custom action */
  onAction?: () => void;
  actionIcon?: keyof typeof Ionicons.glyphMap;
  actionLabel?: string;
  actionColor?: string;
  deleteLabel?: string;
  disabled?: boolean;
  /** New: multiple right-side actions (swipe left to reveal) */
  rightActions?: SwipeAction[];
  /** New: multiple left-side actions (swipe right to reveal) */
  leftActions?: SwipeAction[];
  /** New: long-press callback for accessibility */
  onLongPress?: () => void;
  /** New: whether to enable haptic feedback */
  enableHaptics?: boolean;
}

const SWIPE_THRESHOLD = 80;
const ACTION_WIDTH = 80;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

function SwipeableRowInner({
  children,
  onDelete,
  onAction,
  actionIcon = 'trash-outline',
  actionLabel = 'Delete',
  actionColor,
  deleteLabel,
  disabled = false,
  rightActions = [],
  leftActions = [],
  onLongPress,
  enableHaptics = true,
}: Props) {
  const { colors } = useAppTheme();
  const resolvedActionColor = actionColor ?? colors.danger;
  const translateX = useRef(new Animated.Value(0)).current;
  const isOpen = useRef<'left' | 'right' | null>(null);
  const longPressTimer = useRef<NodeJS.Timeout | null>(null);

  // Calculate total width for multi-action support
  const rightActionsWidth = rightActions.length > 0
    ? rightActions.length * ACTION_WIDTH
    : (onDelete || onAction ? ACTION_WIDTH : 0);
  const leftActionsWidth = leftActions.length * ACTION_WIDTH;

  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gestureState) => {
        if (disabled) return false;
        // Cancel long-press if user starts swiping
        if (longPressTimer.current) {
          clearTimeout(longPressTimer.current);
          longPressTimer.current = null;
        }
        return Math.abs(gestureState.dx) > 10 && Math.abs(gestureState.dy) < 10;
      },
      onPanResponderGrant: () => {
        if (enableHaptics) fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
      },
      onPanResponderMove: (_, gestureState) => {
        // Swipe left (negative dx) - reveal right actions
        if (gestureState.dx < 0 && rightActionsWidth > 0) {
          translateX.setValue(Math.max(gestureState.dx, -rightActionsWidth * 1.2));
        }
        // Swipe right (positive dx) - reveal left actions
        else if (gestureState.dx > 0 && leftActionsWidth > 0) {
          translateX.setValue(Math.min(gestureState.dx, leftActionsWidth * 1.2));
        }
        // Handle closing when swiping in opposite direction
        else if (isOpen.current === 'right' && gestureState.dx > 0) {
          translateX.setValue(Math.min(gestureState.dx - rightActionsWidth, 0));
        }
        else if (isOpen.current === 'left' && gestureState.dx < 0) {
          translateX.setValue(Math.max(gestureState.dx + leftActionsWidth, 0));
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        const shouldOpenRight = gestureState.dx < -SWIPE_THRESHOLD && rightActionsWidth > 0;
        const shouldOpenLeft = gestureState.dx > SWIPE_THRESHOLD && leftActionsWidth > 0;
        const shouldClose = Math.abs(gestureState.dx) < SWIPE_THRESHOLD / 2;

        if (shouldOpenRight && isOpen.current !== 'right') {
          Animated.spring(translateX, {
            toValue: -rightActionsWidth,
            useNativeDriver: true,
            tension: 100,
            friction: 10,
          }).start();
          isOpen.current = 'right';
          if (enableHaptics) fireHaptic(HapticIntent.JUDGMENT_LOCKED);
        } else if (shouldOpenLeft && isOpen.current !== 'left') {
          Animated.spring(translateX, {
            toValue: leftActionsWidth,
            useNativeDriver: true,
            tension: 100,
            friction: 10,
          }).start();
          isOpen.current = 'left';
          if (enableHaptics) fireHaptic(HapticIntent.JUDGMENT_LOCKED);
        } else {
          Animated.spring(translateX, {
            toValue: 0,
            useNativeDriver: true,
            tension: 100,
            friction: 10,
          }).start();
          isOpen.current = null;
        }
      },
    })
  ).current;

  const handleAction = useCallback((action?: SwipeAction) => {
    if (enableHaptics) fireHaptic(HapticIntent.ALERT_TRIGGERED);
    // Animate close first, then call action
    Animated.timing(translateX, {
      toValue: 0,
      duration: 200,
      useNativeDriver: true,
    }).start(() => {
      isOpen.current = null;
      if (action) {
        action.onPress();
      } else if (onAction) {
        onAction();
      } else if (onDelete) {
        onDelete();
      }
    });
  }, [onAction, onDelete, enableHaptics, translateX]);

  const close = useCallback(() => {
    Animated.spring(translateX, {
      toValue: 0,
      useNativeDriver: true,
    }).start();
    isOpen.current = null;
  }, [translateX]);

  const handleLongPress = useCallback(() => {
    if (onLongPress) {
      if (enableHaptics) fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      onLongPress();
    }
  }, [onLongPress, enableHaptics]);

  const handlePressIn = useCallback(() => {
    if (onLongPress && !disabled) {
      longPressTimer.current = setTimeout(handleLongPress, 500);
    }
  }, [onLongPress, disabled, handleLongPress]);

  const handlePressOut = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  // Render right-side actions (revealed on swipe left)
  const renderRightActions = () => {
    if (rightActions.length > 0) {
      return (
        <View style={[styles.actionsContainer, styles.rightActionsContainer]}>
          {rightActions.map((action) => (
            <View key={action.key} style={[styles.actionContainer, { backgroundColor: action.color }]}>
              <Pressable
                style={styles.actionButton}
                onPress={() => handleAction(action)}
                accessibilityRole="button"
                accessibilityLabel={action.label}
              >
                <Ionicons name={action.icon} size={22} color="#fff" />
                <Text style={styles.actionText}>{action.label}</Text>
              </Pressable>
            </View>
          ))}
        </View>
      );
    }
    // Legacy single action
    if (onDelete || onAction) {
      return (
        <View style={[styles.actionContainer, { backgroundColor: resolvedActionColor }]}>
          <Pressable
            style={styles.actionButton}
            onPress={() => handleAction()}
            accessibilityRole="button"
            accessibilityLabel={deleteLabel || actionLabel}
          >
            <Ionicons name={actionIcon} size={22} color="#fff" />
            <Text style={styles.actionText}>{deleteLabel || actionLabel}</Text>
          </Pressable>
        </View>
      );
    }
    return null;
  };

  // Render left-side actions (revealed on swipe right)
  const renderLeftActions = () => {
    if (leftActions.length === 0) return null;
    return (
      <View style={[styles.actionsContainer, styles.leftActionsContainer]}>
        {leftActions.map((action) => (
          <View key={action.key} style={[styles.actionContainer, { backgroundColor: action.color }]}>
            <Pressable
              style={styles.actionButton}
              onPress={() => handleAction(action)}
              accessibilityRole="button"
              accessibilityLabel={action.label}
            >
              <Ionicons name={action.icon} size={22} color="#fff" />
              <Text style={styles.actionText}>{action.label}</Text>
            </Pressable>
          </View>
        ))}
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Left actions (behind the row, revealed on swipe right) */}
      {renderLeftActions()}

      {/* Right actions (behind the row, revealed on swipe left) */}
      {renderRightActions()}

      {/* Swipeable content */}
      <Animated.View
        style={[styles.content, { backgroundColor: colors.background, transform: [{ translateX }] }]}
        {...panResponder.panHandlers}
        onTouchStart={handlePressIn}
        onTouchEnd={handlePressOut}
        onTouchCancel={handlePressOut}
      >
        {children}
      </Animated.View>
    </View>
  );
}

/**
 * Pre-built swipe action creators for common actions
 */
export const SwipeActions = {
  share: (onPress: () => void): SwipeAction => ({
    key: 'share',
    label: 'Share',
    icon: 'share-outline',
    color: '#22c55e',
    onPress,
  }),

  delete: (onPress: () => void): SwipeAction => ({
    key: 'delete',
    label: 'Delete',
    icon: 'trash-outline',
    color: '#ef4444',
    onPress,
  }),

  edit: (onPress: () => void): SwipeAction => ({
    key: 'edit',
    label: 'Edit',
    icon: 'pencil-outline',
    color: '#f59e0b',
    onPress,
  }),

  favorite: (onPress: () => void): SwipeAction => ({
    key: 'favorite',
    label: 'Favorite',
    icon: 'heart-outline',
    color: '#ec4899',
    onPress,
  }),
};

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
  },
  actionsContainer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    flexDirection: 'row',
  },
  rightActionsContainer: {
    right: 0,
  },
  leftActionsContainer: {
    left: 0,
  },
  actionContainer: {
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
    // backgroundColor set dynamically via useAppTheme
  },
});

export const SwipeableRow = React.memo(SwipeableRowInner);
export default SwipeableRow;
