/**
 * WishlistEditTargetModal — Modal for editing target price of a watchlist item.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import type { WatchlistItem } from '@/data/types';

interface WishlistEditTargetModalProps {
  visible: boolean;
  editTargetItem: WatchlistItem | null;
  editTargetValue: string;
  editTargetSaving: boolean;
  onEditTargetValueChange: (v: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export const WishlistEditTargetModal = React.memo(function WishlistEditTargetModal(props: WishlistEditTargetModalProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const {
    visible, editTargetItem, editTargetValue, editTargetSaving,
    onEditTargetValueChange, onSave, onClose,
  } = props;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist_edit_target.title')}</Text>
            <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel={t('wishlist_edit_target.close_a11y')}>
              <Ionicons name="close" size={24} color={colors.muted} />
            </AnimatedPressable>
          </View>

          {editTargetItem && (
            <>
              <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                  {editTargetItem.title}
                </Text>
                {editTargetItem.category && (
                  <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                    <Text style={[styles.categoryText, { color: colors.accent }]}>{editTargetItem.category}</Text>
                  </View>
                )}
              </View>

              <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
              <TextInput
                value={editTargetValue}
                onChangeText={onEditTargetValueChange}
                placeholder="e.g. 350"
                placeholderTextColor={colors.muted}
                keyboardType="numeric"
                autoFocus
                style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                accessibilityLabel={t('wishlist_edit_target.input_a11y')}
              />
              <Text style={[styles.helperText, { color: colors.muted }]}>
                A price alert will be created automatically when you set a target price.
              </Text>

              <AnimatedPressable
                style={[styles.saveBtn, { backgroundColor: colors.accent }]}
                onPress={onSave}
                disabled={editTargetSaving}
                accessibilityRole="button"
                accessibilityLabel={t('wishlist_edit_target.save_a11y')}
              >
                {editTargetSaving ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.saveBtnText}>{t('wishlist_edit_target.save_button')}</Text>
                )}
              </AnimatedPressable>
            </>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
});

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  acquireItemPreview: {
    padding: 14,
    borderRadius: 12,
    marginBottom: 16,
  },
  acquireItemTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '500',
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    borderWidth: 1,
  },
  helperText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 8,
  },
  saveBtn: {
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: 24,
    alignItems: 'center',
  },
  saveBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
