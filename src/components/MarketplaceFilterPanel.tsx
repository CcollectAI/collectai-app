/**
 * Filter panel (full-screen modal) for the marketplace search.
 *
 * Renders source chips, condition chips, price range inputs,
 * sort-by options, and apply/reset controls.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from "react";
import { useTranslation } from "react-i18next";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  Modal,
  StyleSheet,
} from "react-native";
// react-native's own SafeAreaView is iOS-only — it renders as a plain View on
// Android, so content sits under the status bar and gesture nav. Always take it
// from react-native-safe-area-context (see docs/ui-playbook.md).
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

// ── Constants (kept local so component is self-contained) ───────────────

const SOURCE_OPTIONS = [
  "eBay",
  "TCGPlayer",
  "Mercari",
  "Cardmarket",
  "Discogs",
  "StockX",
  "BrickLink",
] as const;

const CONDITION_OPTIONS = [
  "Near Mint",
  "Lightly Played",
  "Played",
  "Poor",
] as const;

const SORT_OPTIONS = [
  { value: "relevance", label: "Relevance" },
  { value: "price_asc", label: "Price: Low\u2192High" },
  { value: "price_desc", label: "Price: High\u2192Low" },
  { value: "newest", label: "Newest" },
] as const;

// ── Props ───────────────────────────────────────────────────────────────

interface MarketplaceFilterPanelProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
  };
  visible: boolean;
  filterSources: string[];
  filterConditions: string[];
  filterMinPrice: string;
  filterMaxPrice: string;
  filterSort: string;
  onSetFilterSources: (sources: string[]) => void;
  onSetFilterConditions: (conditions: string[]) => void;
  onSetFilterMinPrice: (value: string) => void;
  onSetFilterMaxPrice: (value: string) => void;
  onSetFilterSort: (value: string) => void;
  onApply: () => void;
  onClose: () => void;
  onReset: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

function MarketplaceFilterPanelInner({
  theme,
  visible,
  filterSources,
  filterConditions,
  filterMinPrice,
  filterMaxPrice,
  filterSort,
  onSetFilterSources,
  onSetFilterConditions,
  onSetFilterMinPrice,
  onSetFilterMaxPrice,
  onSetFilterSort,
  onApply,
  onClose,
  onReset,
}: MarketplaceFilterPanelProps) {
  const { t } = useTranslation();
  const toggleSource = (src: string) => {
    const active = filterSources.includes(src);
    onSetFilterSources(
      active ? filterSources.filter((s) => s !== src) : [...filterSources, src]
    );
  };

  const toggleCondition = (cond: string) => {
    const active = filterConditions.includes(cond);
    onSetFilterConditions(
      active
        ? filterConditions.filter((c) => c !== cond)
        : [...filterConditions, cond]
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={[s.filterModal, { backgroundColor: theme.background }]}>
        {/* Header */}
        <View style={[s.filterHeader, { borderBottomColor: theme.border }]}>
          <TouchableOpacity onPress={onClose} accessibilityLabel={t('marketplace_filter.close_a11y')}>
            <Ionicons name="close" size={24} color={theme.text} />
          </TouchableOpacity>
          <Text style={[s.filterHeaderTitle, { color: theme.text }]}>Filters</Text>
          <TouchableOpacity onPress={onReset} accessibilityLabel={t('marketplace_filter.reset_a11y')}>
            <Text style={[s.filterResetText, { color: theme.accent }]}>Reset</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={s.filterContent} contentContainerStyle={{ paddingBottom: 32 }}>
          {/* Source filter */}
          <Text style={[s.filterSectionTitle, { color: theme.text }]}>Source</Text>
          <View style={s.filterChipRow}>
            {SOURCE_OPTIONS.map((src) => {
              const active = filterSources.includes(src);
              return (
                <TouchableOpacity
                  key={src}
                  style={[
                    s.filterChip,
                    {
                      borderColor: active ? theme.accent : theme.border,
                      backgroundColor: active ? theme.accent + "20" : "transparent",
                    },
                  ]}
                  onPress={() => toggleSource(src)}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={src}
                >
                  <Text
                    style={[
                      s.filterChipText,
                      { color: active ? theme.accent : theme.text },
                    ]}
                  >
                    {src}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Condition filter */}
          <Text style={[s.filterSectionTitle, { color: theme.text, marginTop: 20 }]}>
            Condition
          </Text>
          <View style={s.filterChipRow}>
            {CONDITION_OPTIONS.map((cond) => {
              const active = filterConditions.includes(cond);
              return (
                <TouchableOpacity
                  key={cond}
                  style={[
                    s.filterChip,
                    {
                      borderColor: active ? theme.accent : theme.border,
                      backgroundColor: active ? theme.accent + "20" : "transparent",
                    },
                  ]}
                  onPress={() => toggleCondition(cond)}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={cond}
                >
                  <Text
                    style={[
                      s.filterChipText,
                      { color: active ? theme.accent : theme.text },
                    ]}
                  >
                    {cond}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Price range */}
          <Text style={[s.filterSectionTitle, { color: theme.text, marginTop: 20 }]}>
            Price range
          </Text>
          <View style={s.filterPriceRow}>
            <TextInput
              value={filterMinPrice}
              onChangeText={onSetFilterMinPrice}
              placeholder="Min"
              placeholderTextColor={theme.muted}
              keyboardType="numeric"
              style={[
                s.filterPriceInput,
                { color: theme.text, borderColor: theme.border },
              ]}
              accessibilityLabel={t('marketplace_filter.min_price_a11y')}
              returnKeyType="done"
              maxLength={10}
            />
            <Text style={[s.filterPriceDash, { color: theme.muted }]}>{"\u2013"}</Text>
            <TextInput
              value={filterMaxPrice}
              onChangeText={onSetFilterMaxPrice}
              placeholder="Max"
              placeholderTextColor={theme.muted}
              keyboardType="numeric"
              style={[
                s.filterPriceInput,
                { color: theme.text, borderColor: theme.border },
              ]}
              accessibilityLabel={t('marketplace_filter.max_price_a11y')}
              returnKeyType="done"
              maxLength={10}
            />
          </View>

          {/* Sort order */}
          <Text style={[s.filterSectionTitle, { color: theme.text, marginTop: 20 }]}>
            Sort by
          </Text>
          <View style={s.filterChipRow}>
            {SORT_OPTIONS.map((opt) => {
              const active = filterSort === opt.value;
              return (
                <TouchableOpacity
                  key={opt.value}
                  style={[
                    s.filterChip,
                    {
                      borderColor: active ? theme.accent : theme.border,
                      backgroundColor: active ? theme.accent + "20" : "transparent",
                    },
                  ]}
                  onPress={() => onSetFilterSort(opt.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: active }}
                  accessibilityLabel={opt.label}
                >
                  <Text
                    style={[
                      s.filterChipText,
                      { color: active ? theme.accent : theme.text },
                    ]}
                  >
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>

        {/* Apply button */}
        <View style={[s.filterFooter, { borderTopColor: theme.border }]}>
          <TouchableOpacity
            style={[s.filterApplyButton, { backgroundColor: theme.accent }]}
            onPress={onApply}
            accessibilityRole="button"
            accessibilityLabel={t('marketplace_filter.apply_a11y')}
          >
            <Text style={s.filterApplyText}>{t('marketplace_filter.apply')}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

export const MarketplaceFilterPanel = React.memo(MarketplaceFilterPanelInner);

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  filterModal: {
    flex: 1,
  },
  filterHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  filterHeaderTitle: {
    fontSize: 17,
    fontWeight: "700",
  },
  filterResetText: {
    fontSize: 14,
    fontWeight: "600",
  },
  filterContent: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  filterSectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 10,
  },
  filterChipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  filterChip: {
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  filterChipText: {
    fontSize: 13,
    fontWeight: "500",
  },
  filterPriceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  filterPriceInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  filterPriceDash: {
    fontSize: 16,
    fontWeight: "600",
  },
  filterFooter: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  filterApplyButton: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  filterApplyText: {
    color: "#FFFFFF", // Button text on brand background
    fontSize: 15,
    fontWeight: "700",
  },
});
