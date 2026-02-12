/**
 * Create / Edit Mandate screen.
 *
 * If ?id= query param is present, loads existing mandate for editing.
 * Otherwise shows a blank create form.
 */

import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Switch,
  KeyboardAvoidingView,
  ActionSheetIOS,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useSettings } from "@/lib/settings";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { collectorsApi } from "@/api/collectorsApi";
import { useToast } from "@/components/Toast";

const CATEGORIES = [
  "pokemon", "mtg", "yugioh", "lorcana", "funko", "lego",
  "warhammer", "retro_games", "manga", "sportscards",
  "designer_toys", "anime_figures", "hot_toys", "gunpla",
  "diecast", "kpop_merch", "disney",
];

const CATEGORY_OPTIONS = ["Any", ...CATEGORIES];

const SOURCES = ["ebay", "tcgplayer", "cardmarket"];

const REGIONS = [
  { value: "", label: "Any Region" },
  { value: "europe", label: "Europe" },
  { value: "americas", label: "Americas" },
  { value: "japan", label: "Japan" },
];

const REGION_LABELS = REGIONS.map((r) => r.label);

const TRUST_OPTIONS = ["0.5", "0.6", "0.7", "0.8", "0.9"];

export default function CreateMandateScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const isEdit = Boolean(params.id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [maxPrice, setMaxPrice] = useState("");
  const [minTrust, setMinTrust] = useState(0.6);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [region, setRegion] = useState("");
  const [status, setStatus] = useState<"active" | "paused">("active");

  // Load existing mandate
  useEffect(() => {
    if (!params.id) return;
    (async () => {
      try {
        const m = await collectorsApi.getMandate(params.id!);
        setName(m.name);
        setCategory(m.category ?? null);
        setMaxPrice(String(m.max_price));
        setMinTrust(m.min_trust_score ?? 0.6);
        setSelectedSources(m.allowed_sources ?? []);
        setRegion(m.region ?? "");
        setStatus(m.status === "paused" ? "paused" : "active");
      } catch {
        showToast({ message: "Failed to load search", type: "error" });
      } finally {
        setLoading(false);
      }
    })();
  }, [params.id]);

  const toggleSource = (s: string) => {
    setSelectedSources((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  // ActionSheetIOS handlers
  const showCategoryPicker = () => {
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", ...CATEGORY_OPTIONS],
          cancelButtonIndex: 0,
          title: "Select Category",
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            const selected = CATEGORY_OPTIONS[buttonIndex - 1];
            setCategory(selected === "Any" ? null : selected);
          }
        }
      );
    } else {
      Alert.alert(
        "Select Category",
        undefined,
        CATEGORY_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => setCategory(opt === "Any" ? null : opt),
        })).concat([{ text: "Cancel", style: "cancel" }])
      );
    }
  };

  const showRegionPicker = () => {
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", ...REGION_LABELS],
          cancelButtonIndex: 0,
          title: "Select Region",
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            setRegion(REGIONS[buttonIndex - 1].value);
          }
        }
      );
    } else {
      Alert.alert(
        "Select Region",
        undefined,
        REGIONS.map((r) => ({
          text: r.label,
          onPress: () => setRegion(r.value),
        })).concat([{ text: "Cancel", style: "cancel" }])
      );
    }
  };

  const showTrustScorePicker = () => {
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", ...TRUST_OPTIONS],
          cancelButtonIndex: 0,
          title: "Select Min Trust Score",
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            setMinTrust(parseFloat(TRUST_OPTIONS[buttonIndex - 1]));
          }
        }
      );
    } else {
      Alert.alert(
        "Select Min Trust Score",
        undefined,
        TRUST_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => setMinTrust(parseFloat(opt)),
        })).concat([{ text: "Cancel", style: "cancel" }])
      );
    }
  };

  const handleSave = useCallback(async () => {
    if (!name.trim() || !maxPrice) {
      showToast({ message: "Please fill in required fields", type: "error" });
      return;
    }

    setSaving(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    try {
      if (isEdit && params.id) {
        await collectorsApi.updateMandate(params.id, {
          name: name.trim(),
          status,
          category: category || undefined,
          max_price: parseFloat(maxPrice),
          min_trust_score: minTrust,
          allowed_sources: selectedSources.length ? selectedSources : undefined,
          region: region || undefined,
        });
        showToast({ message: "Search updated", type: "success" });
      } else {
        await collectorsApi.createMandate({
          name: name.trim(),
          search_query: name.trim(),
          category: category || undefined,
          max_price: parseFloat(maxPrice),
          min_trust_score: minTrust,
          allowed_sources: selectedSources.length ? selectedSources : undefined,
          region: region || undefined,
        });
        showToast({ message: "Search activated", type: "success" });
      }
      router.back();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save";
      showToast({ message: msg, type: "error" });
    } finally {
      setSaving(false);
    }
  }, [name, maxPrice, minTrust, selectedSources, region, category, status, isEdit, params.id]);

  // Derive display label for current region
  const regionLabel = REGIONS.find((r) => r.value === region)?.label ?? "Any Region";

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === "ios" ? 88 : 0}
      >
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={[styles.title, { color: colors.text }]}>
          {isEdit ? "Edit Search" : "New Deal Search"}
        </Text>

        {/* Name */}
        <Text style={[styles.label, { color: colors.muted }]}>NAME</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.card, borderColor: colors.border, color: colors.text }]}
          placeholder="e.g. Pokemon Grails under 200"
          placeholderTextColor={colors.muted}
          value={name}
          onChangeText={setName}
        />

        {/* Category */}
        <Text style={[styles.label, { color: colors.muted }]}>CATEGORY (OPTIONAL)</Text>
        <AnimatedPressable
          style={[styles.pickerRow, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={showCategoryPicker}
        >
          <Text style={[styles.pickerValue, { color: category ? colors.text : colors.muted }]}>
            {category || "Any"}
          </Text>
          <Ionicons name="chevron-down" size={16} color={colors.muted} />
        </AnimatedPressable>

        {/* Max Price */}
        <Text style={[styles.label, { color: colors.muted }]}>MAX PRICE PER ITEM (EUR)</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.card, borderColor: colors.border, color: colors.text }]}
          placeholder="e.g. 400"
          placeholderTextColor={colors.muted}
          keyboardType="decimal-pad"
          value={maxPrice}
          onChangeText={setMaxPrice}
        />

        {/* Min Trust Score */}
        <Text style={[styles.label, { color: colors.muted }]}>
          MIN TRUST SCORE: {minTrust.toFixed(2)}
        </Text>
        <AnimatedPressable
          style={[styles.pickerRow, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={showTrustScorePicker}
        >
          <Text style={[styles.pickerValue, { color: colors.text }]}>
            {minTrust.toFixed(1)}
          </Text>
          <Ionicons name="chevron-down" size={16} color={colors.muted} />
        </AnimatedPressable>
        <Text style={[styles.hint, { color: colors.muted }]}>
          Higher = stricter seller/listing quality filter.
        </Text>

        {/* Marketplace Sources — toggle switches */}
        <Text style={[styles.label, { color: colors.muted }]}>MARKETPLACES</Text>
        {SOURCES.map((s) => {
          const active = selectedSources.includes(s);
          return (
            <View key={s} style={styles.sourceToggleRow}>
              <Text style={[styles.sourceToggleLabel, { color: colors.text }]}>{s}</Text>
              <Switch
                value={active}
                onValueChange={() => toggleSource(s)}
                trackColor={{ false: colors.border, true: colors.accent + "80" }}
                thumbColor={active ? colors.accent : colors.muted}
              />
            </View>
          );
        })}
        <Text style={[styles.hint, { color: colors.muted }]}>
          Leave all unchecked to search all marketplaces.
        </Text>

        {/* Region */}
        <Text style={[styles.label, { color: colors.muted }]}>REGION</Text>
        <AnimatedPressable
          style={[styles.pickerRow, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={showRegionPicker}
        >
          <Text style={[styles.pickerValue, { color: region ? colors.text : colors.muted }]}>
            {regionLabel}
          </Text>
          <Ionicons name="chevron-down" size={16} color={colors.muted} />
        </AnimatedPressable>

        {/* Status toggle (edit mode) */}
        {isEdit && (
          <View style={styles.toggleRow}>
            <Text style={[styles.label, { color: colors.muted, marginBottom: 0 }]}>ACTIVE</Text>
            <Switch
              value={status === "active"}
              onValueChange={(v) => setStatus(v ? "active" : "paused")}
              trackColor={{ false: colors.border, true: colors.accent + "80" }}
              thumbColor={status === "active" ? colors.accent : colors.muted}
            />
          </View>
        )}

        {/* Save Button */}
        <AnimatedPressable
          style={[styles.saveBtn, { backgroundColor: colors.accent, opacity: saving ? 0.6 : 1 }]}
          onPress={handleSave}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel={isEdit ? "Save changes" : "Activate search"}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons name={isEdit ? "checkmark" : "flash"} size={18} color="#fff" />
              <Text style={styles.saveBtnText}>{isEdit ? "Save Changes" : "Activate"}</Text>
            </>
          )}
        </AnimatedPressable>

        {/* Delete (edit mode) */}
        {isEdit && (
          <AnimatedPressable
            style={[styles.deleteBtn, { borderColor: colors.danger }]}
            onPress={async () => {
              try {
                await collectorsApi.deleteMandate(params.id!);
                showToast({ message: "Search paused", type: "success" });
                router.back();
              } catch {
                showToast({ message: "Failed to pause", type: "error" });
              }
            }}
            accessibilityRole="button"
            accessibilityLabel="Pause search"
          >
            <Ionicons name="pause" size={16} color={colors.danger} />
            <Text style={[styles.deleteBtnText, { color: colors.danger }]}>Pause Search</Text>
          </AnimatedPressable>
        )}

        <View style={{ height: Platform.OS === "ios" ? 40 : 24 }} />
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 24 },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center" },

  title: { fontSize: 22, fontWeight: "700", marginBottom: 20 },
  label: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
    marginTop: 16,
  },
  hint: { fontSize: 11, marginTop: 4 },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    fontSize: 15,
  },

  pickerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  pickerValue: {
    fontSize: 15,
    fontWeight: "500",
  },

  sourceToggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 8,
  },
  sourceToggleLabel: {
    fontSize: 15,
    fontWeight: "500",
    textTransform: "capitalize",
  },

  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 20,
  },

  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    borderRadius: 10,
    marginTop: 28,
    gap: 6,
  },
  saveBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },

  deleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 12,
    gap: 6,
  },
  deleteBtnText: { fontSize: 14, fontWeight: "600" },
});
