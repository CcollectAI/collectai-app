/**
 * Price feedback section for item detail screen.
 *
 * Renders "Help improve our estimates" header, sale price input row,
 * "I sold it for..." and "Price seems off" buttons.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { useTranslation } from "react-i18next";
import { View, Text, Pressable, TextInput, StyleSheet } from "react-native";

// ── Props interface ─────────────────────────────────────────────────────

interface PriceFeedbackSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    /** The label colour for anything sitting ON `accent`. Required, not
     *  optional: the whole point is that it is #000000 in high-contrast dark,
     *  so a component that falls back to white reintroduces the bug it was
     *  added to fix. `app/item/[id].tsx` passes the full theme object. */
    accentText: string;
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
  const { t } = useTranslation();
  return (
    <View style={[s.feedbackBlock, { borderTopColor: theme.border }]}>
      {/* Muted and small: the VALUE is now directly above this, so this line
          is a follow-up question about that number rather than the title of a
          section. As a `text`-coloured 14/600 header it read as the heading of
          the whole card, which is how a request for help ended up outranking
          the figure it is about. */}
      <Text style={[s.feedbackHeader, { color: theme.muted }]} accessibilityRole="header">
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
            placeholder={t('price_feedback.sale_price_placeholder')}
            placeholderTextColor={theme.muted ?? "#64748B"}
            keyboardType="decimal-pad"
            value={salePrice}
            onChangeText={onSalePriceChange}
            autoFocus
            accessibilityLabel={t('price_feedback.sale_price_a11y')}
          />
          <Pressable
            onPress={onSubmitSalePrice}
            disabled={submittingFeedback || !salePrice.trim()}
            style={[
              s.feedbackSubmitBtn,
              { backgroundColor: theme.accent, opacity: submittingFeedback ? 0.7 : 1 },
            ]}
            accessibilityRole="button"
            accessibilityLabel={t('price_feedback.submit_a11y')}
          >
            {/* `accentText`, not "#FFFFFF" — the comment that used to sit here
                said "Button text on brand background", which is exactly the
                case the playbook says NOT to hardcode: in high-contrast dark
                the accent is light (#4DA6FF) and accentText is #000000, so
                white was invisible on the primary action. */}
            <Text style={[s.feedbackBtnText, { color: theme.accentText }]}>
              {submittingFeedback ? "..." : "Submit"}
            </Text>
          </Pressable>
          <Pressable
            onPress={onCancelSalePrice}
            style={[s.feedbackCancelBtn, { borderColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={t('price_feedback.cancel_a11y')}
          >
            <Text style={[s.feedbackBtnText, { color: theme.muted }]}>
              Cancel
            </Text>
          </Pressable>
        </View>
      ) : (
        <View style={s.feedbackButtonsRow}>
          {/* Outline, not a filled accent block. This screen has ONE primary
              action — Sell — and a filled data-collection button beside it made
              two. Same target, same label, one tier down.

              It also retires `feedbackBtnTextWhite`, a hardcoded `#FFFFFF`
              whose own comment read "Button text on brand background" — the
              exact defect docs/ui-playbook.md records as fixed in THIS file on
              2026-08-19. One instance was fixed (the sale-price submit, which
              uses `accentText`); this second one was missed, and
              `check:brand-colors` cannot see it because the fill and the colour
              sit in different objects, outside its window. */}
          <Pressable
            onPress={() => onShowSalePriceInput(true)}
            style={[s.feedbackBtn, { borderWidth: 1, borderColor: theme.accent }]}
            accessibilityRole="button"
            accessibilityLabel={t('price_feedback.report_a11y')}
          >
            <Text style={[s.feedbackBtnText, { color: theme.accent }]}>I sold it for...</Text>
          </Pressable>
          <Pressable
            onPress={onPriceDisagree}
            disabled={submittingFeedback}
            style={[
              s.feedbackBtn,
              { backgroundColor: theme.card, borderWidth: 1, borderColor: theme.border },
            ]}
            accessibilityRole="button"
            accessibilityLabel={t('price_feedback.price_off_a11y')}
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
