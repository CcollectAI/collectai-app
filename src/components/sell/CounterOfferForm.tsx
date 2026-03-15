/**
 * CounterOfferForm — Modal for sending a counter-offer in P2P deals.
 * Extracted from sell/[offerId].tsx.
 */

import React from 'react';
import {
  View,
  Text,
  TextInput,
  Modal,
  Pressable,
  ActivityIndicator,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight } from '@/theme/tokens';

type Props = {
  visible: boolean;
  onClose: () => void;
  onSubmit: () => void;
  counterPrice: string;
  onCounterPriceChange: (value: string) => void;
  counterMessage: string;
  onCounterMessageChange: (value: string) => void;
  actionLoading: boolean;
};

function CounterOfferFormInner({
  visible,
  onClose,
  onSubmit,
  counterPrice,
  onCounterPriceChange,
  counterMessage,
  onCounterMessageChange,
  actionLoading,
}: Props) {
  const { colors } = useAppTheme();
  const canSubmit = !actionLoading && counterPrice.trim().length > 0;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Counter-Offer</Text>
            <Pressable onPress={onClose}>
              <Ionicons name="close" size={24} color={colors.muted} />
            </Pressable>
          </View>

          <Text style={[styles.modalLabel, { color: colors.muted }]}>Your price</Text>
          <TextInput
            style={[styles.modalInput, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            value={counterPrice}
            onChangeText={onCounterPriceChange}
            keyboardType="decimal-pad"
            placeholder="0.00"
            placeholderTextColor={colors.muted}
            autoFocus
          />

          <Text style={[styles.modalLabel, { color: colors.muted }]}>Message (optional)</Text>
          <TextInput
            style={[styles.modalTextarea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            value={counterMessage}
            onChangeText={onCounterMessageChange}
            placeholder="Add a message..."
            placeholderTextColor={colors.muted}
            multiline
            maxLength={2000}
          />

          <AnimatedPressable
            onPress={onSubmit}
            disabled={!canSubmit}
            style={[
              styles.modalConfirmBtn,
              { backgroundColor: colors.accent, opacity: canSubmit ? 1 : 0.5 },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Send counter-offer"
          >
            {actionLoading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="swap-horizontal" size={18} color="#fff" />
                <Text style={styles.modalConfirmBtnText}>Send Counter-Offer</Text>
              </>
            )}
          </AnimatedPressable>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

export const CounterOfferForm = React.memo(CounterOfferFormInner);

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalSheet: {
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
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
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
  },
  modalLabel: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    marginBottom: 6,
    marginTop: 8,
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: text.lg,
  },
  modalTextarea: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: text.md,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  modalConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: radius.md,
    marginTop: 20,
  },
  modalConfirmBtnText: {
    color: '#fff',
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
});
