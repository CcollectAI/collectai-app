/**
 * WatchlistAddForm — Form to add a new item to the watchlist.
 */
import React from "react";
import { useTranslation } from "react-i18next";
import { View, Text, TextInput, ActivityIndicator, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { getCurrencySymbol } from "@/lib/format";
import CompactSelect from "@/components/CompactSelect";
import type { CurrencyCode } from "@/data/types";

type WatchlistPriority = 'high' | 'medium' | 'low';

const PRIORITY_CONFIG: Record<WatchlistPriority, { label: string; color: string; bg: string }> = {
  high: { label: "High", color: "#DC2626", bg: "#DC262615" },
  medium: { label: "Medium", color: "#D97706", bg: "#D9770615" },
  low: { label: "Low", color: "#059669", bg: "#05966915" },
};

type ThemeColors = {
  text: string;
  muted: string;
  card: string;
  border: string;
  background: string;
  accent: string;
  brand?: { dark?: string };
};

type Props = {
  colors: ThemeColors;
  currency: CurrencyCode;
  saving: boolean;
  newTitle: string;
  setNewTitle: (v: string) => void;
  newTargetPrice: string;
  setNewTargetPrice: (v: string) => void;
  /** Display name (not slug) of the chosen category, '' when unset. */
  newCategory: string;
  setNewCategory: (v: string) => void;
  /** All selectable category display names. */
  categoryOptions: string[];
  newPriority: WatchlistPriority;
  setNewPriority: (v: WatchlistPriority) => void;
  newNotes: string;
  setNewNotes: (v: string) => void;
  targetPriceRef: React.RefObject<TextInput | null>;
  notesRef: React.RefObject<TextInput | null>;
  onSave: () => void;
  onClose: () => void;
};

export const WatchlistAddForm = React.memo(function WatchlistAddForm({
  colors,
  currency,
  saving,
  newTitle,
  setNewTitle,
  newTargetPrice,
  setNewTargetPrice,
  newCategory,
  setNewCategory,
  categoryOptions,
  newPriority,
  setNewPriority,
  newNotes,
  setNewNotes,
  targetPriceRef,
  notesRef,
  onSave,
  onClose,
}: Props) {
  const { t } = useTranslation();
  return (
    <View style={[styles.addFormCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.addFormHeader}>
        <Text style={[styles.addFormTitle, { color: colors.text }]}>{t('watchlist.add_title')}</Text>
        <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onClose(); }} style={styles.closeFormBtn} accessibilityRole="button" accessibilityLabel={t('watchlist.close_add_a11y')}>
          <Ionicons name="close" size={20} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {/* Title Input */}
      <View style={styles.inputGroup}>
        <Text style={[styles.inputLabel, { color: colors.text }]}>{t('watchlist.item_name_required')}</Text>
        <TextInput
          style={[styles.textInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
          value={newTitle}
          onChangeText={setNewTitle}
          placeholder="e.g., PSA 10 Charizard Base Set"
          placeholderTextColor={colors.muted}
          autoFocus
          returnKeyType="next"
          onSubmitEditing={() => targetPriceRef.current?.focus()}
          maxLength={100}
          accessibilityLabel={t('watchlist.item_name_a11y')}
        />
      </View>

      {/* Target Price Input */}
      <View style={styles.inputGroup}>
        <Text style={[styles.inputLabel, { color: colors.text }]}>Target Price ({currency}) — optional</Text>
        <View style={styles.priceInputRow}>
          <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{getCurrencySymbol(currency)}</Text>
          <TextInput
            ref={targetPriceRef}
            style={[styles.textInput, styles.priceInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
            value={newTargetPrice}
            onChangeText={setNewTargetPrice}
            placeholder="e.g., 500"
            placeholderTextColor={colors.muted}
            keyboardType="decimal-pad"
            returnKeyType="next"
            onSubmitEditing={() => notesRef.current?.focus()}
            accessibilityLabel={`Target price in ${currency}`}
          />
        </View>
        <Text style={[styles.inputHint, { color: colors.muted }]}>{t('watchlist.target_desc')}</Text>
      </View>

      {/* Category — REQUIRED, and not cosmetic.
          This form used to have no category field at all, and the builder sent
          `category: ''`. The snipe check joins a listing to a watchlist row by
          `mh.category = w.category` (or by item_ref, which the builder never
          has), so an empty category means the row can never produce an alert.
          Counted 2026-08-05: 5 of 13 prod rows had an empty category, all of
          them from this screen — which is exactly where the Alerts tab's
          "create an alert" CTA sends people. */}
      <View style={styles.inputGroup}>
        <Text style={[styles.inputLabel, { color: colors.text }]}>Category (required)</Text>
        <CompactSelect
          title="Category"
          value={newCategory || null}
          options={categoryOptions}
          placeholder="Select category"
          onChange={setNewCategory}
          searchable
        />
        <Text style={[styles.inputHint, { color: colors.muted }]}>
          We only match listings inside the category you pick.
        </Text>
      </View>

      {/* Priority Selector */}
      <View style={styles.inputGroup}>
        <Text style={[styles.inputLabel, { color: colors.text }]}>Priority</Text>
        <View style={styles.priorityRow}>
          {(["high", "medium", "low"] as WatchlistPriority[]).map((p) => {
            const config = PRIORITY_CONFIG[p];
            const active = newPriority === p;
            return (
              <AnimatedPressable
                key={p}
                style={[
                  styles.priorityBtn,
                  { borderColor: colors.border, backgroundColor: colors.card },
                  active && { backgroundColor: config.bg, borderColor: config.color },
                ]}
                onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setNewPriority(p); }}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={`${config.label} priority`}
              >
                <Text
                  style={[
                    styles.priorityBtnText,
                    { color: colors.muted },
                    active && { color: config.color, fontWeight: "700" },
                  ]}
                >
                  {config.label}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>
      </View>

      {/* Notes Input */}
      <View style={styles.inputGroup}>
        <Text style={[styles.inputLabel, { color: colors.text }]}>{t('watchlist.notes_optional')}</Text>
        <TextInput
          ref={notesRef}
          style={[styles.textInput, styles.textInputMultiline, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
          value={newNotes}
          onChangeText={setNewNotes}
          placeholder={t('watchlist.notes_placeholder')}
          placeholderTextColor={colors.muted}
          multiline
          numberOfLines={2}
          maxLength={500}
          returnKeyType="done"
          accessibilityLabel="Notes"
        />
      </View>

      {/* Save Button */}
      <AnimatedPressable
        style={[styles.saveBtn, { backgroundColor: colors.accent }, saving && styles.saveBtnDisabled]}
        onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); onSave(); }}
        disabled={saving}
        accessibilityRole="button"
        accessibilityLabel={saving ? 'Saving' : 'Add to watchlist'}
      >
        {saving ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : (
          <>
            <Ionicons name="add-circle" size={20} color="#FFFFFF" />
            <Text style={styles.saveBtnText}>{t('watchlist.add_button')}</Text>
          </>
        )}
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  addFormCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  addFormHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  addFormTitle: {
    fontSize: 18,
    fontWeight: "700",
  },
  closeFormBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  inputHint: {
    fontSize: 11,
    marginTop: 4,
  },
  textInput: {
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  textInputMultiline: {
    minHeight: 60,
    textAlignVertical: "top",
  },
  priceInputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  currencyPrefix: {
    fontSize: 16,
    fontWeight: "600",
    minWidth: 20,
  },
  priceInput: {
    flex: 1,
  },
  priorityRow: {
    flexDirection: "row",
    gap: 8,
  },
  priorityBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
  },
  priorityBtnText: {
    fontSize: 13,
    fontWeight: "500",
  },
  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 4,
  },
  saveBtnDisabled: {
    opacity: 0.7,
  },
  saveBtnText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
});
