/**
 * Price feedback section for item detail screen.
 *
 * Renders "Help improve our estimates" header, sale price input row,
 * "I sold it for..." and "Price seems off" buttons.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { View, Text, Pressable, TextInput, StyleSheet } from "react-native";

// ── Props interface ─────────────────────────────────────────────────────

interface PriceFeedbackSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
    success: string;
  };
  showSalePriceInput: boolean;
  salePrice: string;
  submittingFeedback: boolean;
  feedbackMessage: string | null;
  onShowSalePriceInput: (show: boolean) => void;
  onSalePriceChange: (value: string) => void;
  onSubmitSalePrice: () => void;
  onPriceDisagree: () => void;
  onCancelSalePrice: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

export const PriceFeedbackSection = React.memo(function PriceFeedbackSection({
  theme,
  showSalePriceInput,
  salePrice,
  submittingFeedback,
  feedbackMessage,
  onShowSalePriceInput,
  onSalePriceChange,
  onSubmitSalePrice,
  onPriceDisagree,
  onCancelSalePrice,
}: PriceFeedbackSectionProps) {
  return (
    <View style={[s.feedbackBlock, { borderTopColor: theme.border }]}>
      <Text style={[s.feedbackHeader, { color: theme.text }]} accessibilityRole="header">
        Help improve our estimates
      </Text>

      {feedbackMessage && (
        <Text style={[s.feedbackMessage, { color: theme.accent }]}>
          {feedbackMessage}
        </Text>
      )}

      {showSalePriceInput ? (
        <View style={s.salePriceInputRow}>
          <TextInput
            style={[
              s.salePriceInput,
              {
                color: theme.text,
                borderColor: theme.border,
                backgroundColor: theme.background,
              },
            ]}
            placeholder="Sale price (e.g., 150.00)"
            placeholderTextColor={theme.muted ?? "#64748B"}
            keyboardType="decimal-pad"
            value={salePrice}
            onChangeText={onSalePriceChange}
            autoFocus
            accessibilityLabel="Sale price"
          />
          <Pressable
            onPress={onSubmitSalePrice}
            disabled={submittingFeedback || !salePrice.trim()}
            style={[
              s.feedbackSubmitBtn,
              { backgroundColor: theme.accent, opacity: submittingFeedback ? 0.7 : 1 },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Submit sale price"
          >
            <Text style={[s.feedbackBtnText, { color: "#FFFFFF" }]}>
              {submittingFeedback ? "..." : "Submit"}
            </Text>
          </Pressable>
          <Pressable
            onPress={onCancelSalePrice}
            style={[s.feedbackCancelBtn, { borderColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel="Cancel sale price entry"
          >
            <Text style={[s.feedbackBtnText, { color: theme.muted }]}>
              Cancel
            </Text>
          </Pressable>
        </View>
      ) : (
        <View style={s.feedbackButtonsRow}>
          <Pressable
            onPress={() => onShowSalePriceInput(true)}
            style={[s.feedbackBtn, { backgroundColor: theme.success }]}
            accessibilityRole="button"
            accessibilityLabel="Report sale price"
          >
            <Text style={s.feedbackBtnTextWhite}>I sold it for...</Text>
          </Pressable>
          <Pressable
            onPress={onPriceDisagree}
            disabled={submittingFeedback}
            style={[
              s.feedbackBtn,
              { backgroundColor: theme.card, borderWidth: 1, borderColor: theme.border },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Report price seems off"
          >
            <Text style={[s.feedbackBtnText, { color: theme.text }]}>
              Price seems off
            </Text>
          </Pressable>
        </View>
      )}
    </View>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  feedbackBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#E2E8F0",
  },
  feedbackHeader: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 10,
  },
  feedbackMessage: {
    fontSize: 12,
    marginBottom: 8,
  },
  feedbackButtonsRow: {
    flexDirection: "row",
    gap: 8,
  },
  feedbackBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  feedbackBtnText: {
    fontSize: 13,
    fontWeight: "500",
  },
  feedbackBtnTextWhite: {
    fontSize: 13,
    fontWeight: "500",
    color: "#FFFFFF",
  },
  salePriceInputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  salePriceInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
  },
  feedbackSubmitBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  feedbackCancelBtn: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
});
