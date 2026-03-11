/**
 * ItemsCategoryModal — Modal to bulk-change category of selected items.
 */
import React from 'react';
import { View, Text, ScrollView, Modal, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { CategoryPill } from '@/components/CategoryPill';
import { fireHaptic, HapticIntent } from '@/haptics';

interface ItemsCategoryModalProps {
  visible: boolean;
  selectedCount: number;
  allCategories: string[];
  onChangeCategory: (cat: string) => void;
  onClose: () => void;
}

export const ItemsCategoryModal = React.memo(function ItemsCategoryModal({
  visible,
  selectedCount,
  allCategories,
  onChangeCategory,
  onClose,
}: ItemsCategoryModalProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <AnimatedPressable
        style={styles.modalOverlay}
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          onClose();
        }}
        accessibilityRole="button"
        accessibilityLabel="Close category picker"
      >
        <View style={[styles.modalContent, { backgroundColor: colors.card }]} accessibilityRole="menu">
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>
              Change Category
            </Text>
            <Text style={[styles.modalSubtitle, { color: colors.muted }]}>
              Move {selectedCount} item{selectedCount > 1 ? 's' : ''} to:
            </Text>
          </View>

          <ScrollView style={styles.modalList}>
            {allCategories.map((cat) => (
              <AnimatedPressable
                key={cat}
                style={[styles.modalOption, { borderColor: colors.border }]}
                onPress={() => {
                  fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                  onChangeCategory(cat);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Move to ${cat}`}
              >
                <CategoryPill id={cat} label={cat} />
                <Ionicons name="chevron-forward" size={18} color={colors.muted} />
              </AnimatedPressable>
            ))}
          </ScrollView>

          <AnimatedPressable
            style={[styles.modalCancelBtn, { borderColor: colors.border }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              onClose();
            }}
            accessibilityRole="button"
            accessibilityLabel="Cancel category change"
          >
            <Text style={[styles.modalCancelText, { color: colors.muted }]}>Cancel</Text>
          </AnimatedPressable>
        </View>
      </AnimatedPressable>
    </Modal>
  );
});

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 20,
    paddingBottom: 34,
    maxHeight: '70%',
  },
  modalHeader: {
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  modalSubtitle: {
    fontSize: 14,
  },
  modalList: {
    paddingHorizontal: 20,
  },
  modalOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  modalCancelBtn: {
    marginTop: 16,
    marginHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 16,
    fontWeight: '600',
  },
});
