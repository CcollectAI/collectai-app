/**
 * EventCreatorMenu — Bottom sheet modal with Edit, Duplicate, Cancel actions
 * for event creators.
 */

import React from 'react';
import { View, Text, Modal, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface EventCreatorMenuProps {
  visible: boolean;
  onClose: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onCancel: () => void;
}

export const EventCreatorMenu = React.memo(function EventCreatorMenu({
  visible,
  onClose,
  onEdit,
  onDuplicate,
  onCancel,
}: EventCreatorMenuProps) {
  const { colors } = useAppTheme();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <AnimatedPressable
        style={styles.menuOverlay}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close menu"
      >
        <View style={[styles.menuSheet, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <AnimatedPressable
            style={styles.menuItem}
            onPress={onEdit}
            accessibilityRole="button"
            accessibilityLabel="Edit event"
          >
            <Ionicons name="create-outline" size={20} color={colors.accent} />
            <Text style={[styles.menuItemText, { color: colors.text }]}>Edit Event</Text>
          </AnimatedPressable>

          <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

          <AnimatedPressable
            style={styles.menuItem}
            onPress={onDuplicate}
            accessibilityRole="button"
            accessibilityLabel="Duplicate event"
          >
            <Ionicons name="copy-outline" size={20} color={colors.accent} />
            <Text style={[styles.menuItemText, { color: colors.text }]}>Duplicate Event</Text>
          </AnimatedPressable>

          <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

          <AnimatedPressable
            style={styles.menuItem}
            onPress={onCancel}
            accessibilityRole="button"
            accessibilityLabel="Cancel event"
          >
            <Ionicons name="close-circle-outline" size={20} color={colors.danger} />
            <Text style={[styles.menuItemText, { color: colors.danger }]}>Cancel Event</Text>
          </AnimatedPressable>

          <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

          <AnimatedPressable
            style={styles.menuItem}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Cancel"
          >
            <Text style={[styles.menuItemText, { color: colors.muted }]}>Cancel</Text>
          </AnimatedPressable>
        </View>
      </AnimatedPressable>
    </Modal>
  );
});

const styles = StyleSheet.create({
  menuOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  menuSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderBottomWidth: 0,
    paddingVertical: 8,
    paddingBottom: 32,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  menuItemText: {
    fontSize: 16,
    fontWeight: '500',
  },
  menuDivider: {
    height: 1,
    marginHorizontal: 16,
  },
});
