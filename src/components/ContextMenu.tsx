/**
 * ContextMenu Component
 * An accessible alternative to swipe actions, triggered via long-press.
 * Displays a bottom sheet with action options.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  Pressable,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import type { SwipeAction } from './SwipeableRow';

type ContextMenuProps = {
  visible: boolean;
  onClose: () => void;
  actions: SwipeAction[];
  title?: string;
  subtitle?: string;
};

export function ContextMenu({
  visible,
  onClose,
  actions,
  title,
  subtitle,
}: ContextMenuProps) {
  const { colors } = useAppTheme();

  const handleActionPress = (action: SwipeAction) => {
    onClose();
    // Small delay to let modal close animation complete
    setTimeout(() => {
      action.onPress();
    }, 200);
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <Pressable style={styles.overlay} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close menu">
        <Pressable
          style={[styles.menuContainer, { backgroundColor: colors.card }]}
          onPress={(e) => e.stopPropagation()}
          accessibilityRole="none"
        >
          <SafeAreaView>
            {/* Header */}
            {(title || subtitle) && (
              <View style={[styles.header, { borderBottomColor: colors.border }]}>
                {title && (
                  <Text
                    style={[styles.title, { color: colors.text }]}
                    numberOfLines={1}
                  >
                    {title}
                  </Text>
                )}
                {subtitle && (
                  <Text
                    style={[styles.subtitle, { color: colors.muted }]}
                    numberOfLines={1}
                  >
                    {subtitle}
                  </Text>
                )}
              </View>
            )}

            {/* Actions */}
            <View style={styles.actionsContainer}>
              {actions.map((action, index) => (
                <Pressable
                  key={action.key}
                  style={[
                    styles.actionRow,
                    index < actions.length - 1 && {
                      borderBottomWidth: StyleSheet.hairlineWidth,
                      borderBottomColor: colors.border,
                    },
                  ]}
                  onPress={() => handleActionPress(action)}
                  accessibilityRole="button"
                  accessibilityLabel={action.label}
                >
                  <View style={[styles.actionIcon, { backgroundColor: action.color + '20' }]}>
                    <Ionicons name={action.icon} size={20} color={action.color} />
                  </View>
                  <Text style={[styles.actionLabel, { color: colors.text }]}>
                    {action.label}
                  </Text>
                  <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                </Pressable>
              ))}
            </View>

            {/* Cancel button */}
            <Pressable
              style={[styles.cancelButton, { backgroundColor: colors.background }]}
              onPress={onClose}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            >
              <Text style={[styles.cancelText, { color: colors.accent }]}>Cancel</Text>
            </Pressable>
          </SafeAreaView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  menuContainer: {
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 8,
  },
  header: {
    padding: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  subtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  actionsContainer: {
    paddingVertical: 8,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  actionIcon: {
    width: 36,
    height: 36,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionLabel: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
  },
  cancelButton: {
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 8,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  cancelText: {
    fontSize: 16,
    fontWeight: '600',
  },
});

export default ContextMenu;
