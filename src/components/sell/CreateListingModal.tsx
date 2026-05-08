/**
 * CreateListingModal — Modal for creating a new marketplace listing
 * with fee preview (backend + local fallback).
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TextInput,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';
import { formatPrice, getCurrencySymbol } from '@/lib/format';
import { radius, text, fontWeight, gap } from '@/theme/tokens';
import type { useFormField } from '@/hooks/useFormField';
import type { MarketplaceId, MarketplaceFeeSchedule, CurrencyCode } from '@/data/types';

const MARKETPLACE_CONFIG: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  collectai: { label: 'Sparrow P2P', icon: 'people-outline', color: '#81D8D0' },
  ebay: { label: 'eBay', icon: 'cart-outline', color: '#E53238' },
  mercari: { label: 'Mercari', icon: 'storefront-outline', color: '#4DC8F0' },
  cardmarket: { label: 'Cardmarket', icon: 'card-outline', color: '#1A3C7D' },
};

interface CreateListingModalProps {
  visible: boolean;
  onClose: () => void;
  titleField: ReturnType<typeof useFormField>;
  priceField: ReturnType<typeof useFormField>;
  marketplace: MarketplaceId;
  onMarketplaceChange: (mp: MarketplaceId) => void;
  feeSchedules: MarketplaceFeeSchedule[];
  currency: CurrencyCode;
  creating: boolean;
  onCreateListing: () => void;
}

export const CreateListingModal = React.memo(function CreateListingModal({
  visible,
  onClose,
  titleField,
  priceField,
  marketplace,
  onMarketplaceChange,
  feeSchedules,
  currency,
  creating,
  onCreateListing,
}: CreateListingModalProps) {
  const { colors } = useAppTheme();

  // Local fee preview
  const feePreview = useMemo(() => {
    const price = parseFloat(priceField.value.replace(/[^\d.]/g, ''));
    if (!Number.isFinite(price) || price <= 0) return null;
    const schedule = feeSchedules.find((f) => f.marketplaceId === marketplace);
    if (!schedule) return null;
    const fees = (price * (schedule.baseFeePct + schedule.paymentProcessingPct) / 100) + schedule.fixedFee;
    return { fees: Math.round(fees * 100) / 100, net: Math.round((price - fees) * 100) / 100 };
  }, [priceField.value, marketplace, feeSchedules]);

  // Backend fee preview (debounced)
  const [backendFeePreview, setBackendFeePreview] = useState<{ fees: number; net: number } | null>(null);

  useEffect(() => {
    const price = parseFloat(priceField.value.replace(/[^\d.]/g, ''));
    if (!Number.isFinite(price) || price <= 0 || !visible) {
      setBackendFeePreview(null);
      return;
    }
    const timer = setTimeout(() => {
      collectorsApi.calculateMarketplaceFees({ price, marketplace_id: marketplace, category: undefined })
        .then((data: any) => {
          if (data?.total_fees != null) {
            setBackendFeePreview({ fees: data.total_fees, net: price - data.total_fees });
          }
        })
        .catch((err) => logger.warn('[CreateListingModal] fee calc failed, using local:', err));
    }, 500);
    return () => clearTimeout(timer);
  }, [priceField.value, marketplace, visible]);

  const displayFees = backendFeePreview ?? feePreview;

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Create Listing</Text>
            <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.muted} />
            </AnimatedPressable>
          </View>

          <Text style={[styles.modalLabel, { color: colors.text }]}>Title</Text>
          <TextInput
            style={[styles.modalInput, { backgroundColor: colors.background, borderColor: titleField.touched && titleField.error ? colors.danger : colors.border, color: colors.text }]}
            value={titleField.value}
            onChangeText={titleField.onChange}
            onBlur={titleField.onBlur}
            placeholder="Item title"
            placeholderTextColor={colors.muted}
            autoFocus
            returnKeyType="next"
            maxLength={200}
          />
          {titleField.touched && titleField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{titleField.error}</Text>}

          <Text style={[styles.modalLabel, { color: colors.text }]}>Price ({currency})</Text>
          <TextInput
            style={[styles.modalInput, { backgroundColor: colors.background, borderColor: priceField.touched && priceField.error ? colors.danger : colors.border, color: colors.text }]}
            value={priceField.value}
            onChangeText={priceField.onChange}
            onBlur={priceField.onBlur}
            placeholder={`${getCurrencySymbol(currency)} 0.00`}
            placeholderTextColor={colors.muted}
            keyboardType="decimal-pad"
            returnKeyType="done"
          />
          {priceField.touched && priceField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{priceField.error}</Text>}

          <Text style={[styles.modalLabel, { color: colors.text }]}>Marketplace</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
            {(['collectai', 'ebay', 'mercari', 'cardmarket'] as MarketplaceId[]).map((mp) => {
              const cfg = MARKETPLACE_CONFIG[mp];
              const isActive = marketplace === mp;
              return (
                <Pressable
                  key={mp}
                  onPress={() => onMarketplaceChange(mp)}
                  style={[styles.mpChip, { borderColor: isActive ? cfg?.color ?? colors.accent : colors.border }, isActive && { backgroundColor: (cfg?.color ?? colors.accent) + '15' }]}
                >
                  <Text style={[styles.mpChipText, { color: isActive ? cfg?.color ?? colors.accent : colors.muted }]}>{cfg?.label ?? mp}</Text>
                </Pressable>
              );
            })}
          </ScrollView>

          {/* Fee preview — prefer backend calculation, fall back to local */}
          {displayFees && (
            <View style={[styles.feePreview, { backgroundColor: colors.background, borderColor: colors.border }]}>
              <View style={styles.feeRow}>
                <Text style={[styles.feeLabel, { color: colors.muted }]}>Est. fees{backendFeePreview ? '' : ' (local)'}</Text>
                <Text style={[styles.feeValue, { color: colors.error }]}>-{formatPrice(displayFees.fees, currency)}</Text>
              </View>
              <View style={styles.feeRow}>
                <Text style={[styles.feeLabel, { color: colors.muted }]}>Est. net</Text>
                <Text style={[styles.feeValue, { color: colors.success }]}>{formatPrice(displayFees.net, currency)}</Text>
              </View>
            </View>
          )}

          <AnimatedPressable
            style={[styles.createBtn, { backgroundColor: colors.accent }, creating && { opacity: 0.7 }]}
            onPress={onCreateListing}
            disabled={creating}
            accessibilityRole="button"
            accessibilityLabel={creating ? 'Creating listing' : 'Create listing'}
          >
            {creating ? (
              <ActivityIndicator size="small" color={colors.accentText} />
            ) : (
              <Text style={[styles.createBtnText, { color: colors.accentText }]}>Create as Draft</Text>
            )}
          </AnimatedPressable>
        </View>
      </View>
    </Modal>
  );
});

const styles = StyleSheet.create({
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.4)' },
  modalContent: { borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: 20, paddingBottom: 40 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: text.xl, fontWeight: fontWeight.bold },
  modalLabel: { fontSize: text.md, fontWeight: fontWeight.semibold, marginBottom: 6, marginTop: gap.md },
  modalInput: { borderRadius: radius.sm, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10, fontSize: text.lg, marginBottom: gap.md },
  mpChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.md, borderWidth: 1, marginRight: gap.md },
  mpChipText: { fontSize: text.sm, fontWeight: fontWeight.semibold },
  feePreview: { borderRadius: radius.sm, borderWidth: 1, padding: 12, marginBottom: gap.xl },
  feeRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  feeLabel: { fontSize: text.sm },
  feeValue: { fontSize: text.md, fontWeight: fontWeight.semibold },
  createBtn: { borderRadius: radius.md, paddingVertical: 14, alignItems: 'center', justifyContent: 'center' },
  createBtnText: { fontSize: text.lg, fontWeight: fontWeight.bold },
  fieldError: { fontSize: text.sm, marginTop: 2, marginLeft: 4, marginBottom: 4 },
});
