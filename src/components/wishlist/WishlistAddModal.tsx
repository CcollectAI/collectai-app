/**
 * WishlistAddModal — Modal form for adding a new watchlist item.
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

interface WishlistAddModalProps {
  visible: boolean;
  saving: boolean;
  formTitle: string;
  formCategory: string;
  formTargetPrice: string;
  formNotes: string;
  onFormTitleChange: (v: string) => void;
  onFormTargetPriceChange: (v: string) => void;
  onFormNotesChange: (v: string) => void;
  onOpenCategoryPicker: () => void;
  onAdd: () => void;
  onClose: () => void;
}

export const WishlistAddModal = React.memo(function WishlistAddModal(props: WishlistAddModalProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const {
    visible, saving,
    formTitle, formCategory, formTargetPrice, formNotes,
    onFormTitleChange, onFormTargetPriceChange, onFormNotesChange,
    onOpenCategoryPicker, onAdd, onClose,
  } = props;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist.add_title')}</Text>
            <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel={t('wishlist.close_add_a11y')}>
              <Ionicons name="close" size={24} color={colors.muted} />
            </AnimatedPressable>
          </View>

          <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.title_required')}</Text>
          <TextInput
            value={formTitle}
            onChangeText={onFormTitleChange}
            placeholder="e.g. Charizard VMAX Rainbow"
            placeholderTextColor={colors.muted}
            style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            accessibilityLabel={t('wishlist.item_title_a11y')}
          />

          <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.category_required')}</Text>
          <AnimatedPressable
            style={[styles.input, styles.pickerBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
            onPress={onOpenCategoryPicker}
            accessibilityRole="button"
            accessibilityLabel={formCategory ? `Category: ${formCategory}. Tap to change` : 'Select category'}
          >
            <Text style={{ color: formCategory ? colors.text : colors.muted }}>
              {formCategory || 'Select category'}
            </Text>
            <Ionicons name="chevron-down" size={18} color={colors.muted} />
          </AnimatedPressable>

          <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
          <TextInput
            value={formTargetPrice}
            onChangeText={onFormTargetPriceChange}
            placeholder="e.g. 350"
            placeholderTextColor={colors.muted}
            keyboardType="numeric"
            style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            accessibilityLabel={t('wishlist.target_price_a11y')}
          />

          <Text style={[styles.label, { color: colors.text }]}>Notes</Text>
          <TextInput
            value={formNotes}
            onChangeText={onFormNotesChange}
            placeholder="e.g. Looking for PSA 9 or higher"
            placeholderTextColor={colors.muted}
            multiline
            numberOfLines={3}
            style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            accessibilityLabel="Notes"
          />

          <AnimatedPressable
            style={[styles.saveBtn, { backgroundColor: colors.accent }]}
            onPress={onAdd}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel={t('wishlist.add_button_a11y')}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.saveBtnText}>{t('wishlist.add_title')}</Text>
            )}
          </AnimatedPressable>
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
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  pickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
