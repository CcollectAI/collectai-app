import React, { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  Pressable,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";

type SaveState = "idle" | "saving" | "success" | "error";

// Pull from single source of truth — show top categories as chips, rest in "Other"
import { CATEGORIES as ALL_CATS } from '@/constants/categories';

const ICON_MAP: Record<string, string> = {
  pokemon: 'flash-outline', mtg: 'sparkles-outline', yugioh: 'layers-outline',
  lorcana: 'star-outline', funko: 'cube-outline', lego: 'grid-outline',
  warhammer: 'skull-outline', gunpla: 'rocket-outline', retro_games: 'game-controller-outline',
  manga: 'book-outline', sportscards: 'football-outline', designer_toys: 'color-palette-outline',
  anime_figures: 'person-outline', hot_toys: 'flame-outline', diecast: 'car-outline',
  kpop_merch: 'musical-notes-outline', taylor_swift: 'musical-note-outline',
  disney: 'heart-outline', keycaps: 'keypad-outline', one_piece: 'boat-outline',
};

const CATEGORY_CHIPS = [
  ...ALL_CATS.map((c) => ({
    label: c.name,
    icon: ICON_MAP[c.slug] ?? 'pricetag-outline',
  })),
  { label: 'Other', icon: 'ellipsis-horizontal' },
];

// Common condition grades for quick selection
const CONDITION_CHIPS = [
  { label: "Mint", short: "M" },
  { label: "Near Mint", short: "NM" },
  { label: "Excellent", short: "EX" },
  { label: "Good", short: "G" },
  { label: "PSA 10", short: "10" },
  { label: "PSA 9", short: "9" },
  { label: "Raw", short: "Raw" },
];

const ManualAddScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [gameOrSeries, setGameOrSeries] = useState("");
  const [conditionGrade, setConditionGrade] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [estimatedValue, setEstimatedValue] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);

  const canSubmit = name.trim().length > 0 && saveState !== "saving";

  const handleCategoryChip = (label: string) => {
    if (label === "Other") {
      setCategory("");
    } else {
      setCategory(label);
    }
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;

    const client: any = supabase as any;
    if (!client || typeof client.from !== "function") {
      setSaveState("error");
      setErrorText(
        "Supabase client not configured. Manual entries are in demo mode only."
      );
      return;
    }

    setSaveState("saving");
    setErrorText(null);

    try {
      const purchase = purchasePrice ? Number(purchasePrice) : null;
      const estimated = estimatedValue ? Number(estimatedValue) : null;

      const { error } = await client.from("portfolio_items").insert([
        {
          name: name.trim(),
          category: category.trim() || null,
          game_or_series: gameOrSeries.trim() || null,
          condition_grade: conditionGrade.trim() || null,
          purchase_price: Number.isNaN(purchase as number) ? null : purchase,
          estimated_value: Number.isNaN(estimated as number) ? null : estimated,
          currency: "EUR",
          source: source.trim() || null,
          notes: notes.trim() || null,
        },
      ]);

      if (error) {
        console.warn("[ManualAdd] insert error:", error.message);
        setSaveState("error");
        setErrorText(error.message || "Failed to save item.");
        return;
      }

      setSaveState("success");
      setName("");
      setCategory("");
      setGameOrSeries("");
      setConditionGrade("");
      setPurchasePrice("");
      setEstimatedValue("");
      setSource("");
      setNotes("");
    } catch (err: any) {
      console.warn("[ManualAdd] unexpected error:", err);
      setSaveState("error");
      setErrorText(err?.message || "Unexpected error while saving item.");
    } finally {
      setTimeout(() => {
        setSaveState("idle");
      }, 2000);
    }
  };

  const bannerContent = (() => {
    if (saveState === "saving")
      return { type: "info" as const, text: "Saving item…" };
    if (saveState === "success")
      return {
        type: "success" as const,
        text: "Item saved successfully!",
      };
    if (saveState === "error")
      return {
        type: "error" as const,
        text: errorText || "Something went wrong while saving.",
      };
    return null;
  })();

  const getBannerColors = (type: string) => {
    if (type === "error") {
      return { bg: "#FEF2F2", border: "#EF4444", icon: "warning-outline" as const, iconColor: "#EF4444" };
    }
    if (type === "success") {
      return { bg: colors.accent + "15", border: colors.accent, icon: "checkmark-circle-outline" as const, iconColor: colors.accent };
    }
    return { bg: "#FEF3C7", border: "#F59E0B", icon: "time-outline" as const, iconColor: "#F59E0B" };
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
      >
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Add Manually</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={animatedStyle}>
            {/* Intro Card */}
            <View style={[styles.introCard, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
              <View style={[styles.introIconWrap, { backgroundColor: colors.accent + '20' }]}>
                <Ionicons name="create-outline" size={20} color={colors.accent} />
              </View>
              <View style={styles.introText}>
                <Text style={[styles.introTitle, { color: colors.text }]}>Manual Entry</Text>
                <Text style={[styles.introSubtitle, { color: colors.muted }]}>
                  Enter item details yourself for full control
                </Text>
              </View>
            </View>

            {/* Status banner */}
            {bannerContent && (
              <View
                style={[
                  styles.banner,
                  {
                    backgroundColor: getBannerColors(bannerContent.type).bg,
                    borderColor: getBannerColors(bannerContent.type).border,
                  },
                ]}
              >
                <View style={styles.bannerIconBox}>
                  {saveState === "saving" ? (
                    <ActivityIndicator size="small" color={colors.accent} />
                  ) : (
                    <Ionicons
                      name={getBannerColors(bannerContent.type).icon}
                      size={18}
                      color={getBannerColors(bannerContent.type).iconColor}
                    />
                  )}
                </View>
                <Text style={[styles.bannerText, { color: colors.text }]}>
                  {bannerContent.text}
                </Text>
              </View>
            )}

            {/* Section: Basic Info */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Basic Information</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Name */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Item name <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={name}
                      onChangeText={setName}
                      placeholder="e.g. Charizard GX (Alt Art)"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                    />
                  </View>
                </View>

                {/* Category Chips */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Category</Text>
                  <View style={styles.chipRow}>
                    {CATEGORY_CHIPS.map((chip) => {
                      const isSelected = category === chip.label || (chip.label === "Other" && category === "");
                      return (
                        <AnimatedPressable
                          key={chip.label}
                          style={[
                            styles.chip,
                            {
                              backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                              borderColor: isSelected ? colors.accent : colors.border,
                            },
                          ]}
                          onPress={() => handleCategoryChip(chip.label)}
                        >
                          <Ionicons
                            name={chip.icon as any}
                            size={14}
                            color={isSelected ? colors.accent : colors.muted}
                          />
                          <Text
                            style={[
                              styles.chipText,
                              { color: isSelected ? colors.accent : colors.text },
                            ]}
                          >
                            {chip.label}
                          </Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                  {category !== "" && !CATEGORY_CHIPS.find(c => c.label === category) && (
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background, marginTop: 8 }]}>
                      <Ionicons name="pricetag-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                      <TextInput
                        value={category}
                        onChangeText={setCategory}
                        placeholder="Custom category"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                      />
                    </View>
                  )}
                </View>

                {/* Game / Series */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Set / Series</Text>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="albums-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={gameOrSeries}
                      onChangeText={setGameOrSeries}
                      placeholder="e.g. Scarlet & Violet, Master Grade"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                    />
                  </View>
                </View>
              </View>
            </View>

            {/* Section: Condition & Value */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="diamond-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Condition & Value</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Condition */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Condition / Grade</Text>
                  <View style={styles.chipRow}>
                    {CONDITION_CHIPS.map((chip) => {
                      const isSelected = conditionGrade === chip.label;
                      return (
                        <AnimatedPressable
                          key={chip.label}
                          style={[
                            styles.conditionChip,
                            {
                              backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                              borderColor: isSelected ? colors.accent : colors.border,
                            },
                          ]}
                          onPress={() => setConditionGrade(chip.label)}
                        >
                          <Text
                            style={[
                              styles.conditionChipText,
                              { color: isSelected ? colors.accent : colors.text },
                            ]}
                          >
                            {chip.short}
                          </Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                  {conditionGrade && !CONDITION_CHIPS.find(c => c.label === conditionGrade) && (
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background, marginTop: 8 }]}>
                      <Ionicons name="ribbon-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                      <TextInput
                        value={conditionGrade}
                        onChangeText={setConditionGrade}
                        placeholder="Custom condition"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                      />
                    </View>
                  )}
                </View>

                {/* Prices */}
                <View style={styles.fieldRow}>
                  <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Purchase Price</Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>€</Text>
                      <TextInput
                        value={purchasePrice}
                        onChangeText={setPurchasePrice}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                      />
                    </View>
                  </View>
                  <View style={[styles.fieldBlock, { flex: 1 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Estimated Value</Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>€</Text>
                      <TextInput
                        value={estimatedValue}
                        onChangeText={setEstimatedValue}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                      />
                    </View>
                  </View>
                </View>
              </View>
            </View>

            {/* Section: Additional Details */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="document-text-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Additional Details</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Source */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Source</Text>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="storefront-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={source}
                      onChangeText={setSource}
                      placeholder="Twitch stream, local shop, Cardmarket…"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                    />
                  </View>
                </View>

                {/* Notes */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Notes</Text>
                  <View style={[styles.inputWrapMultiline, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <TextInput
                      value={notes}
                      onChangeText={setNotes}
                      multiline
                      numberOfLines={3}
                      placeholder="Print line, story, plans, etc."
                      placeholderTextColor={colors.muted}
                      style={[styles.inputMultiline, { color: colors.text }]}
                      textAlignVertical="top"
                    />
                  </View>
                </View>
              </View>
            </View>

            {/* Submit Button */}
            <AnimatedPressable
              onPress={handleSubmit}
              disabled={!canSubmit}
              style={[
                styles.submitButton,
                {
                  backgroundColor: canSubmit ? colors.accent : colors.border,
                },
              ]}
            >
              {saveState === "saving" ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                  <Text style={styles.submitButtonText}>Save to Collection</Text>
                </>
              )}
            </AnimatedPressable>

            {/* Footer hint */}
            <View style={styles.footerHint}>
              <Ionicons name="bulb-outline" size={14} color={colors.muted} />
              <Text style={[styles.footerHintText, { color: colors.muted }]}>
                Tip: Use QuickScan for faster entry with AI assistance
              </Text>
            </View>

            <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: "600",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  introCard: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 20,
  },
  introIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  introText: {
    flex: 1,
  },
  introTitle: {
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 2,
  },
  introSubtitle: {
    fontSize: 13,
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  bannerText: {
    fontSize: 13,
    flex: 1,
    fontWeight: "500",
  },
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  fieldBlock: {
    marginBottom: 14,
  },
  fieldRow: {
    flexDirection: "row",
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  inputWrap: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  inputWrapMultiline: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minHeight: 88,
  },
  inputIcon: {
    marginRight: 8,
  },
  currencyPrefix: {
    fontSize: 14,
    fontWeight: "600",
    marginRight: 4,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  inputMultiline: {
    flex: 1,
    fontSize: 14,
    minHeight: 64,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  chipText: {
    fontSize: 13,
    fontWeight: "500",
  },
  conditionChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 44,
    alignItems: 'center',
  },
  conditionChipText: {
    fontSize: 12,
    fontWeight: "600",
  },
  submitButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 4,
  },
  submitButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  footerHint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 16,
  },
  footerHintText: {
    fontSize: 12,
  },
});

export default ManualAddScreen;
