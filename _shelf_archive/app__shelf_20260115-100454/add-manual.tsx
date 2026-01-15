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
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import supabase from "@/lib/supabaseClient";
import { useAppTheme } from "@/hooks/useAppTheme";
type SaveState = "idle" | "saving" | "success" | "error";

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

const ManualAddScreen: React.FC = () => {
  const colors = useAppColors();

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
      return { type: "info" as const, text: "Saving item to Supabase…" };
    if (saveState === "success")
      return {
        type: "success" as const,
        text: "Item saved to your portfolio_items table.",
      };
    if (saveState === "error")
      return {
        type: "error" as const,
        text:
          errorText ||
          "Something went wrong while saving. Check Supabase later.",
      };
    return null;
  })();

  const bannerColors =
    bannerContent?.type === "error"
      ? { bg: "#FDECEC", border: "#D64545", icon: "warning-outline" as const }
      : bannerContent?.type === "success"
      ? {
          bg: "#E7F6F8",
          border: "#19A7AE",
          icon: "checkmark-circle-outline" as const,
        }
      : {
          bg: "#FFF7E6",
          border: "#F59E0B",
          icon: "time-outline" as const,
        };

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.headerLabel, { color: colors.muted }]}>
              Add item
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Manual entry
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              Quick way to log a card, figure or kit manually. Data is written
              into the portfolio_items table so we can use it later for value
              tracking and analytics.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons
              name="create-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Status banner */}
        {bannerContent && (
          <View
            style={[
              styles.banner,
              {
                backgroundColor: bannerColors.bg,
                borderColor: bannerColors.border,
              },
            ]}
          >
            <View style={styles.bannerIconBox}>
              {saveState === "saving" ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <Ionicons
                  name={bannerColors.icon}
                  size={18}
                  color={bannerColors.border}
                />
              )}
            </View>
            <Text style={[styles.bannerText, { color: colors.text }]}>
              {bannerContent.text}
            </Text>
          </View>
        )}

        {/* Form */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          {/* Name */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>
              Item name *
            </Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="e.g. Charizard GX (Alt Art)"
              placeholderTextColor="#A0B3C4"
              style={[
                styles.input,
                {
                  borderColor: colors.border,
                  backgroundColor: "#FFFFFF",
                  color: colors.text,
                },
              ]}
            />
          </View>

          {/* Category + game/series */}
          <View style={styles.fieldRow}>
            <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
              <Text style={[styles.fieldLabel, { color: colors.text }]}>
                Category
              </Text>
              <TextInput
                value={category}
                onChangeText={setCategory}
                placeholder="Pokémon, Funko, LEGO…"
                placeholderTextColor="#A0B3C4"
                style={[
                  styles.input,
                  {
                    borderColor: colors.border,
                    backgroundColor: "#FFFFFF",
                    color: colors.text,
                  },
                ]}
              />
            </View>
            <View style={[styles.fieldBlock, { flex: 1 }]}>
              <Text style={[styles.fieldLabel, { color: colors.text }]}>
                Game / series
              </Text>
              <TextInput
                value={gameOrSeries}
                onChangeText={setGameOrSeries}
                placeholder="Set or line (e.g. MH3, One Piece)"
                placeholderTextColor="#A0B3C4"
                style={[
                  styles.input,
                  {
                    borderColor: colors.border,
                    backgroundColor: "#FFFFFF",
                    color: colors.text,
                  },
                ]}
              />
            </View>
          </View>

          {/* Condition */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>
              Condition / grade
            </Text>
            <TextInput
              value={conditionGrade}
              onChangeText={setConditionGrade}
              placeholder="Raw, Near Mint, PSA 9…"
              placeholderTextColor="#A0B3C4"
              style={[
                styles.input,
                {
                  borderColor: colors.border,
                  backgroundColor: "#FFFFFF",
                  color: colors.text,
                },
              ]}
            />
          </View>

          {/* Prices */}
          <View style={styles.fieldRow}>
            <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
              <Text style={[styles.fieldLabel, { color: colors.text }]}>
                Purchase price (EUR)
              </Text>
              <TextInput
                value={purchasePrice}
                onChangeText={setPurchasePrice}
                keyboardType="decimal-pad"
                placeholder="e.g. 120"
                placeholderTextColor="#A0B3C4"
                style={[
                  styles.input,
                  {
                    borderColor: colors.border,
                    backgroundColor: "#FFFFFF",
                    color: colors.text,
                  },
                ]}
              />
            </View>
            <View style={[styles.fieldBlock, { flex: 1 }]}>
              <Text style={[styles.fieldLabel, { color: colors.text }]}>
                Estimated value (EUR)
              </Text>
              <TextInput
                value={estimatedValue}
                onChangeText={setEstimatedValue}
                keyboardType="decimal-pad"
                placeholder="e.g. 240"
                placeholderTextColor="#A0B3C4"
                style={[
                  styles.input,
                  {
                    borderColor: colors.border,
                    backgroundColor: "#FFFFFF",
                    color: colors.text,
                  },
                ]}
              />
            </View>
          </View>

          {/* Source */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>
              Source
            </Text>
            <TextInput
              value={source}
              onChangeText={setSource}
              placeholder="Twitch stream, local shop, Cardmarket…"
              placeholderTextColor="#A0B3C4"
              style={[
                styles.input,
                {
                  borderColor: colors.border,
                  backgroundColor: "#FFFFFF",
                  color: colors.text,
                },
              ]}
            />
          </View>

          {/* Notes */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>
              Notes
            </Text>
            <TextInput
              value={notes}
              onChangeText={setNotes}
              multiline
              placeholder="Print line, story, plans, etc."
              placeholderTextColor="#A0B3C4"
              style={[
                styles.input,
                styles.inputMultiline,
                {
                  borderColor: colors.border,
                  backgroundColor: "#FFFFFF",
                  color: colors.text,
                  textAlignVertical: "top",
                },
              ]}
            />
          </View>

          {/* Submit button */}
          <Pressable
            onPress={handleSubmit}
            disabled={!canSubmit}
            style={[
              styles.submitButton,
              {
                backgroundColor: canSubmit ? colors.accent : "#D6E4EC",
              },
            ]}
          >
            {saveState === "saving" ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <Ionicons name="save-outline" size={16} color="#FFFFFF" />
                <Text style={styles.submitButtonText}>Save item</Text>
              </>
            )}
          </Pressable>

          <Text style={[styles.footerText, { color: colors.muted }]}>
            Later we can auto-fill this from QuickScan or marketplace imports.
            For now, this gives you a real table with real items to build on.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLabel: {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    fontWeight: "600",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 2,
  },
  headerSub: {
    fontSize: 12,
    marginTop: 4,
    maxWidth: 280,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#D6E4EC",
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  bannerText: {
    fontSize: 12,
    flex: 1,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  fieldBlock: {
    marginBottom: 12,
  },
  fieldRow: {
    flexDirection: "row",
    marginBottom: 4,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
  },
  inputMultiline: {
    minHeight: 72,
  },
  submitButton: {
    marginTop: 8,
    borderRadius: 999,
    paddingVertical: 10,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 6,
  },
  submitButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  footerText: {
    marginTop: 10,
    fontSize: 11,
  },
});

export default ManualAddScreen;
