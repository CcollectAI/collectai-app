/**
 * WishlistAcquireModal — "I Got It!" modal for converting watchlist item to collection.
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

interface WishlistAcquireModalProps {
  visible: boolean;
  acquireItem: WatchlistItem | null;
  acquirePrice: string;
  acquireNotes: string;
  acquiring: boolean;
  onAcquirePriceChange: (v: string) => void;
  onAcquireNotesChange: (v: string) => void;
  onConfirm: () => void;
  onClose: () => void;
}

export const WishlistAcquireModal = React.memo(function WishlistAcquireModal(props: WishlistAcquireModalProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const {
    visible, acquireItem, acquirePrice, acquireNotes, acquiring,
    onAcquirePriceChange, onAcquireNotesChange, onConfirm, onClose,
  } = props;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist.acquire_title')}</Text>
            <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel={t('wishlist.close_acquire_a11y')}>
              <Ionicons name="close" size={24} color={colors.muted} />
            </AnimatedPressable>
          </View>

          {acquireItem && (
            <>
              <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                  {acquireItem.title}
                </Text>
                {acquireItem.category && (
                  <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                    <Text style={[styles.categoryText, { color: colors.accent }]}>{acquireItem.category}</Text>
                  </View>
                )}
              </View>

              <Text style={[styles.label, { color: colors.text }]}>What did you pay? ({settings.currency})</Text>
              <TextInput
                value={acquirePrice}
                onChangeText={onAcquirePriceChange}
                placeholder={acquireItem.targetPrice ? `Target was ${acquireItem.targetPrice}` : 'e.g. 150'}
                placeholderTextColor={colors.muted}
                keyboardType="numeric"
                style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                accessibilityLabel={t('wishlist.price_paid_a11y')}
              />
              <Text style={[styles.helperText, { color: colors.muted }]}>
                This helps improve price predictions for everyone
              </Text>

              <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.notes_optional')}</Text>
              <TextInput
                value={acquireNotes}
                onChangeText={onAcquireNotesChange}
                placeholder="e.g. Found at local shop, great condition"
                placeholderTextColor={colors.muted}
                multiline
                numberOfLines={2}
                style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                accessibilityLabel={t('wishlist.acquire_notes_a11y')}
              />

              <AnimatedPressable
                style={[styles.acquireBtn, { backgroundColor: colors.accent }]}
                onPress={onConfirm}
                disabled={acquiring}
                accessibilityRole="button"
                accessibilityLabel={t('wishlist.acquire_button_a11y')}
              >
                {acquiring ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#fff" />
                    <Text style={styles.acquireBtnText}>{t('wishlist.acquire_button')}</Text>
                  </>
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
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  helperText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 8,
  },
  acquireBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: 24,
    gap: 8,
  },
  acquireBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
