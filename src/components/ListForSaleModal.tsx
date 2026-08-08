/**
 * ListForSaleModal — Multi-marketplace listing modal.
 *
 * Slides up from the bottom and allows users to:
 * - Select one or more marketplaces (checkboxes)
 * - Set per-marketplace prices with live fee previews
 * - Choose listing format (Fixed Price / Auction / Best Offer)
 * - Pick item condition (Mint / Near Mint / Good / Fair / Poor)
 * - Submit listings to all selected marketplaces at once
 */

import React, { useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  TextInput,
  Pressable,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice, getCurrencySymbol, parseMoney } from '@/lib/format';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import {
  useListForSale,
  MARKETPLACE_OPTIONS,
  LISTING_FORMATS,
  CONDITION_LABELS,
} from '@/hooks/useListForSale';
import type { MarketplaceId } from '@/data/types';
import type { ConditionLabel } from '@/hooks/useListForSale';
import { radius, text as textToken, fontWeight as fw, shadow } from '@/theme/tokens';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type ListForSaleModalProps = {
  /** Return value from useListForSale hook. */
  hook: ReturnType<typeof useListForSale>;
  /** Callback after successful submission. */
  onSuccess?: () => void;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ListForSaleModalInner({ hook, onSuccess }: ListForSaleModalProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const {
    visible,
    marketplaces,
    selectedIds,
    format,
    condition,
    feeBreakdowns,
    submitting,
    error,
    canSubmit,
    close,
    toggleMarketplace,
    setMarketplacePrice,
    setFormat,
    setCondition,
    submit,
    calculateFee,
  } = hook;

  const handleSubmit = useCallback(async () => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    const ok = await submit();
    if (ok) {
      onSuccess?.();
    }
  }, [submit, onSuccess, settings.hapticsEnabled]);

  /** Returns an error message if the price string is invalid, or null if valid/empty. */
  const validatePrice = useCallback((price: string): string | null => {
    if (!price || price.trim() === '') return null;
    const num = parseMoney(price) ?? NaN;
    if (isNaN(num)) return 'Enter a valid number';
    if (num <= 0) return 'Price must be greater than 0';
    if (num > 999_999_999) return 'Price is too high';
    return null;
  }, []);

  /** Map of marketplace IDs to their price validation errors. */
  const priceErrors = useMemo(() => {
    const errors: Record<string, string | null> = {};
    for (const mp of MARKETPLACE_OPTIONS) {
      const priceStr = marketplaces[mp.id]?.price ?? '';
      const isSelected = marketplaces[mp.id]?.selected ?? false;
      if (isSelected) {
        errors[mp.id] = validatePrice(priceStr);
      }
    }
    return errors;
  }, [marketplaces, validatePrice]);

  const hasAnyPriceError = useMemo(
    () => Object.values(priceErrors).some((e) => e != null),
    [priceErrors],
  );

  const handleToggle = useCallback(
    (mpId: MarketplaceId) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      toggleMarketplace(mpId);
    },
    [toggleMarketplace, settings.hapticsEnabled],
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={close}
    >
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.overlay}>
          <Pressable style={styles.overlayBackdrop} onPress={close} accessibilityRole="button" accessibilityLabel="Close listing modal" />
          <View style={[styles.sheet, { backgroundColor: colors.card }]}>
            {/* ── Header ──────────────────────────────────────────── */}
            <View style={styles.header}>
              <View style={styles.headerLeft}>
                <Ionicons name="storefront-outline" size={20} color={colors.accent} />
                <Text style={[styles.headerTitle, { color: colors.text }]}>
                  List for Sale
                </Text>
              </View>
              <Pressable
                onPress={close}
                hitSlop={12}
                accessibilityRole="button"
                accessibilityLabel="Close"
              >
                <Ionicons name="close" size={24} color={colors.muted} />
              </Pressable>
            </View>

            {/* Handle indicator */}
            <View style={[styles.handle, { backgroundColor: colors.border }]} />

            <ScrollView
              style={styles.scrollBody}
              contentContainerStyle={styles.scrollContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >
              {/* ── Marketplace Selector ──────────────────────────── */}
              <Text style={[styles.sectionLabel, { color: colors.text }]}>
                Marketplaces
              </Text>
              <Text style={[styles.sectionHint, { color: colors.muted }]}>
                Select where you want to list this item
              </Text>

              {MARKETPLACE_OPTIONS.map((mp) => {
                const isSelected = marketplaces[mp.id]?.selected ?? false;
                const priceStr = marketplaces[mp.id]?.price ?? '';
                const fee = isSelected ? calculateFee(mp.id, priceStr) : null;

                return (
                  <View key={mp.id} style={styles.mpBlock}>
                    {/* Checkbox row */}
                    <Pressable
                      onPress={() => handleToggle(mp.id)}
                      style={styles.mpRow}
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: isSelected }}
                      accessibilityLabel={`${mp.label} marketplace`}
                    >
                      <View
                        style={[
                          styles.checkbox,
                          { borderColor: isSelected ? mp.color : colors.border },
                          isSelected && { backgroundColor: mp.color },
                        ]}
                      >
                        {isSelected && (
                          <Ionicons name="checkmark" size={14} color="#FFFFFF" />
                        )}
                      </View>
                      <Ionicons
                        name={mp.icon as keyof typeof Ionicons.glyphMap}
                        size={18}
                        color={isSelected ? mp.color : colors.muted}
                      />
                      <Text
                        style={[
                          styles.mpLabel,
                          { color: isSelected ? colors.text : colors.muted },
                        ]}
                      >
                        {mp.label}
                      </Text>
                      <Text style={[styles.mpFeeBadge, { color: colors.muted }]}>
                        ~{mp.defaultFeePct}% fee
                      </Text>
                    </Pressable>

                    {/* Price input + fee preview (shown when selected) */}
                    {isSelected && (
                      <View
                        style={[
                          styles.mpPriceSection,
                          { backgroundColor: colors.background, borderColor: colors.border },
                        ]}
                      >
                        <View style={styles.priceInputRow}>
                          <Text style={[styles.currencyPrefix, { color: colors.muted }]}>
                            {getCurrencySymbol(settings.currency)}
                          </Text>
                          <TextInput
                            style={[
                              styles.priceInput,
                              { color: colors.text },
                              priceErrors[mp.id] ? { borderBottomWidth: 1, borderBottomColor: colors.danger } : undefined,
                            ]}
                            value={priceStr}
                            onChangeText={(t) => setMarketplacePrice(mp.id, t)}
                            keyboardType="decimal-pad"
                            placeholder="0.00"
                            placeholderTextColor={colors.muted}
                            returnKeyType="done"
                            accessibilityLabel={`Price for ${mp.label}`}
                          />
                        </View>
                        {priceErrors[mp.id] && (
                          <Text style={[styles.priceError, { color: colors.danger }]}>
                            {priceErrors[mp.id]}
                          </Text>
                        )}

                        {fee && (
                          <View style={styles.feePreviewRow}>
                            <View style={styles.feeItem}>
                              <Text style={[styles.feeLabel, { color: colors.muted }]}>
                                Fees
                              </Text>
                              <Text style={[styles.feeValue, { color: colors.danger }]}>
                                -{formatPrice(fee.totalFees, settings.currency)}
                              </Text>
                            </View>
                            <View style={[styles.feeDivider, { backgroundColor: colors.border }]} />
                            <View style={styles.feeItem}>
                              <Text style={[styles.feeLabel, { color: colors.muted }]}>
                                You receive
                              </Text>
                              <Text style={[styles.feeValue, { color: colors.success }]}>
                                {formatPrice(fee.netProceeds, settings.currency)}
                              </Text>
                            </View>
                          </View>
                        )}
                      </View>
                    )}
                  </View>
                );
              })}

              {/* ── Listing Format ────────────────────────────────── */}
              <Text style={[styles.sectionLabel, { color: colors.text, marginTop: 20 }]}>
                Listing Format
              </Text>

              <View style={styles.formatRow}>
                {LISTING_FORMATS.map((fmt) => {
                  const isActive = format === fmt.value;
                  return (
                    <Pressable
                      key={fmt.value}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        setFormat(fmt.value);
                      }}
                      style={[
                        styles.formatChip,
                        { borderColor: isActive ? colors.accent : colors.border },
                        isActive && { backgroundColor: colors.accent + '15' },
                      ]}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: isActive }}
                      accessibilityLabel={fmt.label}
                    >
                      <View
                        style={[
                          styles.radio,
                          { borderColor: isActive ? colors.accent : colors.border },
                        ]}
                      >
                        {isActive && (
                          <View style={[styles.radioDot, { backgroundColor: colors.accent }]} />
                        )}
                      </View>
                      <Text
                        style={[
                          styles.formatLabel,
                          { color: isActive ? colors.accent : colors.text },
                        ]}
                      >
                        {fmt.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>

              {/* ── Condition Selector ────────────────────────────── */}
              <Text style={[styles.sectionLabel, { color: colors.text, marginTop: 20 }]}>
                Condition
              </Text>

              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.conditionRow}
              >
                {CONDITION_LABELS.map((c) => {
                  const isActive = condition === c;
                  return (
                    <Pressable
                      key={c}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        setCondition(c);
                      }}
                      style={[
                        styles.conditionChip,
                        { borderColor: isActive ? colors.accent : colors.border },
                        isActive && { backgroundColor: colors.accent + '15' },
                      ]}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: isActive }}
                      accessibilityLabel={`Condition: ${c}`}
                    >
                      <Text
                        style={[
                          styles.conditionLabel,
                          { color: isActive ? colors.accent : colors.text },
                          isActive && { fontWeight: fw.bold },
                        ]}
                      >
                        {c}
                      </Text>
                    </Pressable>
                  );
                })}
              </ScrollView>

              {/* ── Fee Comparison Summary ────────────────────────── */}
              {feeBreakdowns.length > 1 && (
                <View
                  style={[
                    styles.comparisonCard,
                    { backgroundColor: colors.background, borderColor: colors.border },
                  ]}
                >
                  <Text style={[styles.comparisonTitle, { color: colors.text }]}>
                    Fee Comparison
                  </Text>
                  {feeBreakdowns.map((fb) => {
                    const mp = MARKETPLACE_OPTIONS.find((o) => o.id === fb.marketplaceId);
                    return (
                      <View key={fb.marketplaceId} style={styles.comparisonRow}>
                        <View style={styles.comparisonLeft}>
                          <View
                            style={[styles.comparisonDot, { backgroundColor: mp?.color ?? colors.accent }]}
                          />
                          <Text style={[styles.comparisonMpName, { color: colors.text }]}>
                            {mp?.label ?? fb.marketplaceId}
                          </Text>
                        </View>
                        <View style={styles.comparisonRight}>
                          <Text style={[styles.comparisonFees, { color: colors.danger }]}>
                            -{formatPrice(fb.totalFees, settings.currency)}
                          </Text>
                          <Text style={[styles.comparisonNet, { color: colors.success }]}>
                            {formatPrice(fb.netProceeds, settings.currency)}
                          </Text>
                        </View>
                      </View>
                    );
                  })}
                </View>
              )}

              {/* ── Error Message ─────────────────────────────────── */}
              {error && (
                <View style={[styles.errorBanner, { backgroundColor: colors.dangerBg }]}>
                  <Ionicons name="alert-circle" size={16} color={colors.danger} />
                  <Text style={[styles.errorText, { color: colors.danger }]}>{error}</Text>
                </View>
              )}
            </ScrollView>

            {/* ── Submit Button (sticky footer) ──────────────────── */}
            <View style={[styles.footer, { borderTopColor: colors.border }]}>
              <AnimatedPressable
                onPress={handleSubmit}
                disabled={!canSubmit || submitting || hasAnyPriceError}
                style={[
                  styles.submitBtn,
                  { backgroundColor: colors.accent },
                  (!canSubmit || submitting || hasAnyPriceError) && { opacity: 0.5 },
                ]}
                accessibilityRole="button"
                accessibilityLabel={
                  submitting
                    ? 'Creating listings'
                    : selectedIds.length === 0
                      ? 'Select a marketplace first'
                      : `List on ${selectedIds.length} marketplace${selectedIds.length > 1 ? 's' : ''}`
                }
              >
                {submitting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Ionicons name="pricetag" size={18} color="#FFFFFF" />
                    <Text style={styles.submitBtnText}>
                      {selectedIds.length === 0
                        ? 'Select a Marketplace'
                        : `List on ${selectedIds.length} Marketplace${selectedIds.length > 1 ? 's' : ''}`}
                    </Text>
                  </>
                )}
              </AnimatedPressable>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  overlayBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  sheet: {
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    maxHeight: '92%',
    ...shadow.floating,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: -8,
    marginBottom: 8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 4,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: textToken.xl,
    fontWeight: fw.bold,

  },

  scrollBody: {
    flexShrink: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
  },

  // ── Section labels ──────────────────────────────────────────────────
  sectionLabel: {
    fontSize: textToken.md,
    fontWeight: fw.bold,

    marginBottom: 4,
  },
  sectionHint: {
    fontSize: textToken.sm,
    marginBottom: 12,
  },

  // ── Marketplace block ───────────────────────────────────────────────
  mpBlock: {
    marginBottom: 8,
  },
  mpRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    gap: 10,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: radius.xs,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mpLabel: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,

    flex: 1,
  },
  mpFeeBadge: {
    fontSize: textToken.xs,
    fontWeight: fw.medium,
  },

  // ── Per-marketplace price section ───────────────────────────────────
  mpPriceSection: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 12,
    marginLeft: 32,
    marginBottom: 4,
  },
  priceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  currencyPrefix: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  priceError: {
    fontSize: textToken.xs,
    fontWeight: fw.medium,
    marginTop: 4,
  },
  priceInput: {
    flex: 1,
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
    paddingVertical: 4,

  },
  feePreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 12,
  },
  feeItem: {
    flex: 1,
    alignItems: 'center',
  },
  feeLabel: {
    fontSize: textToken.xs,
    marginBottom: 2,
  },
  feeValue: {
    fontSize: textToken.md,
    fontWeight: fw.bold,

  },
  feeDivider: {
    width: 1,
    height: 28,
  },

  // ── Listing format ──────────────────────────────────────────────────
  formatRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  formatChip: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  radio: {
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  formatLabel: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,

  },

  // ── Condition selector ──────────────────────────────────────────────
  conditionRow: {
    gap: 8,
    paddingVertical: 8,
  },
  conditionChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  conditionLabel: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,

  },

  // ── Fee comparison card ─────────────────────────────────────────────
  comparisonCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 14,
    marginTop: 20,
  },
  comparisonTitle: {
    fontSize: textToken.md,
    fontWeight: fw.bold,

    marginBottom: 10,
  },
  comparisonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  comparisonLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  comparisonDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  comparisonMpName: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
  },
  comparisonRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  comparisonFees: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
  comparisonNet: {
    fontSize: textToken.md,
    fontWeight: fw.bold,
  },

  // ── Error banner ────────────────────────────────────────────────────
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    borderRadius: radius.sm,
    marginTop: 12,
  },
  errorText: {
    fontSize: textToken.md,
    fontWeight: fw.medium,
    flex: 1,
  },

  // ── Footer / Submit ─────────────────────────────────────────────────
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: radius.md,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontSize: textToken.lg,
    fontWeight: fw.bold,

  },
});

export const ListForSaleModal = React.memo(ListForSaleModalInner);
