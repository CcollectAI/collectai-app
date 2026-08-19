/**
 * Create / Edit Mandate screen.
 *
 * If ?id= query param is present, loads existing mandate for editing.
 * Otherwise shows a blank create form.
 */

import React, { useEffect, useState, useCallback } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
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
import { useFormField, validateAll } from "@/hooks/useFormField";
import { compose, required, maxLength, positiveNumber } from "@/lib/validate";
import { QuickNavBar } from '@/components/QuickNavBar';
import { SelectField, type SelectOption } from '@/components/form/SelectField';

import { CATEGORIES as ALL_CATS } from '@/constants/categories';
import { safeGoBack } from '@/lib/goBack';
import type { CatalogMatchHit } from '@/api/itemsApi';

const CATEGORY_OPTIONS: SelectOption[] = [
  { label: 'Any', value: '' },
  ...ALL_CATS.map((c) => ({ label: c.slug, value: c.slug })),
];

const SOURCES = [
  "ebay", "tcgplayer", "cardmarket", "mercari",
  "discogs", "stockx", "bricklink",
];

const REGION_OPTIONS: SelectOption[] = [
  { value: "", label: "Any Region" },
  { value: "americas", label: "Americas" },
  { value: "europe", label: "Europe" },
  { value: "japan", label: "Japan" },
  { value: "korea", label: "Korea" },
  { value: "oceania", label: "Oceania" },
];

const TRUST_OPTIONS: SelectOption[] = [
  { label: "0.5", value: "0.5" },
  { label: "0.6", value: "0.6" },
  { label: "0.7", value: "0.7" },
  { label: "0.8", value: "0.8" },
  { label: "0.9", value: "0.9" },
];

export default function CreateMandateScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Create Mandate">
      <CreateMandateScreen />
    </ScreenErrorBoundary>
  );
}

function CreateMandateScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const isEdit = Boolean(params.id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);

  // Form state
  const nameField = useFormField(compose(required("Name"), maxLength("Name", 255)));
  const [category, setCategory] = useState<string | null>(null);
  const maxPriceField = useFormField(compose(required("Max price"), positiveNumber("Max price")));
  const [minTrust, setMinTrust] = useState(0.6);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [region, setRegion] = useState("");
  const [status, setStatus] = useState<"active" | "paused">("active");

  // The catalogue item this search is VALUED against — the bare key from
  // /catalog/match. Optional: without it the mandate still runs and still finds
  // deals, it just cannot report savings, because the agent falls back to an
  // ILIKE on the search string which returns one prediction for the whole query.
  const [canonicalKey, setCanonicalKey] = useState<string | null>(null);
  const [matchTitle, setMatchTitle] = useState<string | null>(null);
  // The name the key was picked FOR. If the name later changes, the key is
  // stale and would value the search against a different item than the one the
  // user is now describing — the exact silent-wrong-key failure the picker
  // exists to avoid. Cleared on edit rather than guessed.
  const [matchedForName, setMatchedForName] = useState<string | null>(null);
  const [matches, setMatches] = useState<CatalogMatchHit[] | null>(null);
  const [matching, setMatching] = useState(false);

  // Load existing mandate
  useEffect(() => {
    if (!params.id) return;
    (async () => {
      try {
        // camelCase: getMandate() camelises the snake_case API response so it
        // matches PurchaseMandate (src/data/types.ts). This block read
        // m.max_price / m.min_trust_score / m.allowed_sources, which became
        // undefined the moment that mapping landed — opening a search to edit
        // showed a blank max price and silently reset trust to the 0.6 default,
        // then saved those over the user's real settings. Fixed same day.
        const m = await collectorsApi.getMandate(params.id!) as { name?: string; category?: string; maxPrice?: number; minTrustScore?: number; allowedSources?: string[]; region?: string; status?: string; canonicalRef?: string | null };
        nameField.setValue(m.name ?? '');
        setCategory(m.category ?? null);
        maxPriceField.setValue(m.maxPrice != null ? String(m.maxPrice) : '');
        setMinTrust(m.minTrustScore ?? 0.6);
        setSelectedSources(m.allowedSources ?? []);
        setRegion(m.region ?? "");
        setStatus(m.status === "paused" ? "paused" : "active");
        // The API stores the NAMESPACED ref ("pokemon:base1-base1-1"); the
        // picker and the write path both speak the BARE key, so strip the
        // prefix back off. Sending the namespaced form back would be
        // double-prefixed by the resolver.
        if (m.canonicalRef) {
          const bare = m.canonicalRef.includes(':') ? m.canonicalRef.split(':').slice(1).join(':') : m.canonicalRef;
          setCanonicalKey(bare);
          setMatchTitle(bare);
          setMatchedForName((m.name ?? '').trim());
        }
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

  const handleCategoryChange = useCallback((value: string) => {
    setCategory(value || null);
  }, []);

  const handleRegionChange = useCallback((value: string) => {
    setRegion(value);
  }, []);

  const handleTrustChange = useCallback((value: string) => {
    setMinTrust(parseFloat(value));
  }, []);

  const handleSave = useCallback(async () => {
    if (!validateAll(nameField, maxPriceField)) return;

    setSaving(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Explicit null on edit CLEARS the key server-side; undefined would be
    // dropped by model_dump(exclude_none=True) and read as "not sent".
    const keyPayload = canonicalKey ?? null;

    try {
      if (isEdit && params.id) {
        await collectorsApi.updateMandate(params.id, {
          name: nameField.value.trim(),
          status,
          category: category || undefined,
          max_price: parseFloat(maxPriceField.value),
          min_trust_score: minTrust,
          allowed_sources: selectedSources.length ? selectedSources : undefined,
          region: region || undefined,
          canonical_key: keyPayload,
        });
        showToast({ message: "Search updated", type: "success" });
      } else {
        await collectorsApi.createMandate({
          name: nameField.value.trim(),
          search_query: nameField.value.trim(),
          category: category || undefined,
          max_price: parseFloat(maxPriceField.value),
          min_trust_score: minTrust,
          allowed_sources: selectedSources.length ? selectedSources : undefined,
          region: region || undefined,
          canonical_key: keyPayload,
        });
        showToast({ message: "Search activated", type: "success" });
      }
      safeGoBack(router);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save";
      showToast({ message: msg, type: "error" });
    } finally {
      setSaving(false);
    }
  }, [nameField, maxPriceField, minTrust, selectedSources, region, category, status, isEdit, params.id, canonicalKey]);

  // Look the typed name up in the catalogue. Requires a category: /catalog/match
  // scopes by it, and an unscoped match would return a Pokemon card for
  // "Daytona". Best + alternatives are shown rather than auto-picking, because
  // a wrong key silently values the mandate against the wrong item.
  const runMatch = useCallback(async () => {
    const q = nameField.value.trim();
    if (!q || !category) {
      showToast({ message: "Add a name and a category first", type: "error" });
      return;
    }
    setMatching(true);
    try {
      const res = await collectorsApi.matchCatalog(q, category);
      const all = [res?.best, ...(res?.alternatives ?? [])].filter(
        (h): h is CatalogMatchHit => !!h && !!h.item_key,
      );
      // `best` is frequently ALSO the first alternative. Left as-is that
      // renders the same item twice and hands React two identical keys.
      const seen = new Set<string>();
      const hits = all.filter((h) => !seen.has(h.item_key!) && seen.add(h.item_key!));
      setMatches(hits);
      if (!hits.length) showToast({ message: "No catalogue match — the search still works without one" });
    } catch {
      showToast({ message: "Catalogue lookup failed", type: "error" });
    } finally {
      setMatching(false);
    }
  }, [nameField.value, category, showToast]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
        <QuickNavBar />
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
        <Text style={[styles.label, { color: colors.text }]}>NAME</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.card, borderColor: nameField.touched && nameField.error ? colors.danger : colors.border, color: colors.text }]}
          placeholder="e.g. Pokemon Grails under 200"
          placeholderTextColor={colors.muted}
          value={nameField.value}
          onChangeText={(v) => {
            nameField.onChange(v);
            // Drop a key that was picked for a different name.
            if (matchedForName !== null && v.trim() !== matchedForName) {
              setCanonicalKey(null);
              setMatchTitle(null);
              setMatchedForName(null);
              setMatches(null);
            }
          }}
          onBlur={nameField.onBlur}
          accessibilityLabel="Search name"
        />
        {nameField.touched && nameField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{nameField.error}</Text>}

        {/* Category */}
        <View style={styles.selectGap}>
          <SelectField
            label="CATEGORY (OPTIONAL)"
            value={category ?? ''}
            options={CATEGORY_OPTIONS}
            onChange={handleCategoryChange}
            placeholder="Any"
          />
        </View>

        {/* Value against a catalogue item — optional, and honest about why.
            A mandate without one still finds deals; it just cannot report what
            it saved, because the agent prices every result off an ILIKE on the
            search string. */}
        <Text style={[styles.label, { color: colors.text }]}>VALUE AGAINST (OPTIONAL)</Text>
        {canonicalKey ? (
          <View style={[styles.matchPicked, { backgroundColor: colors.card, borderColor: colors.accent }]}>
            <Ionicons name="pricetag" size={15} color={colors.accent} />
            <Text style={[styles.matchPickedText, { color: colors.text }]} numberOfLines={2}>
              {matchTitle ?? canonicalKey}
            </Text>
            <AnimatedPressable
              onPress={() => { setCanonicalKey(null); setMatchTitle(null); setMatches(null); }}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Remove catalogue match"
            >
              <Ionicons name="close-circle" size={18} color={colors.muted} />
            </AnimatedPressable>
          </View>
        ) : (
          <>
            <AnimatedPressable
              onPress={runMatch}
              disabled={matching}
              style={[styles.matchBtn, { borderColor: colors.border, backgroundColor: colors.card }]}
              accessibilityRole="button"
              accessibilityLabel="Find this item in the catalogue"
            >
              {matching
                ? <ActivityIndicator size="small" color={colors.accent} />
                : <Ionicons name="search" size={15} color={colors.accent} />}
              <Text style={[styles.matchBtnText, { color: colors.accent }]}>
                {matching ? "Searching the catalogue…" : "Find this item in the catalogue"}
              </Text>
            </AnimatedPressable>
            <Text style={[styles.matchHint, { color: colors.muted }]}>
              Links the search to a known item so we can show what a deal saved you.
              Leave it out and the search still runs.
            </Text>
          </>
        )}

        {matches && !canonicalKey ? (
          <View style={styles.matchList}>
            {matches.slice(0, 5).map((h) => (
              <AnimatedPressable
                key={h.item_key!}
                onPress={() => {
                  setCanonicalKey(h.item_key!);
                  setMatchTitle(h.title ?? h.item_key!);
                  setMatchedForName(nameField.value.trim());
                  setMatches(null);
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                }}
                style={[styles.matchRow, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel={`Value against ${h.title ?? h.item_key}`}
              >
                <Text style={[styles.matchRowTitle, { color: colors.text }]} numberOfLines={1}>
                  {h.title ?? h.item_key}
                </Text>
                {h.brand ? (
                  <Text style={[styles.matchRowMeta, { color: colors.muted }]}>{h.brand}</Text>
                ) : null}
              </AnimatedPressable>
            ))}
          </View>
        ) : null}

        {/* Max Price */}
        <Text style={[styles.label, { color: colors.text }]}>MAX PRICE PER ITEM ({settings.currency})</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.card, borderColor: maxPriceField.touched && maxPriceField.error ? colors.danger : colors.border, color: colors.text }]}
          placeholder="e.g. 400"
          placeholderTextColor={colors.muted}
          keyboardType="decimal-pad"
          value={maxPriceField.value}
          onChangeText={maxPriceField.onChange}
          onBlur={maxPriceField.onBlur}
          accessibilityLabel="Maximum price per item"
        />
        {maxPriceField.touched && maxPriceField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{maxPriceField.error}</Text>}

        {/* Min Trust Score */}
        <View style={styles.selectGap}>
          <SelectField
            label={`MIN TRUST SCORE: ${minTrust.toFixed(2)}`}
            value={minTrust.toFixed(1)}
            options={TRUST_OPTIONS}
            onChange={handleTrustChange}
          />
        </View>
        <Text style={[styles.hint, { color: colors.muted }]}>
          Higher = stricter seller/listing quality filter.
        </Text>

        {/* Marketplace Sources — toggle switches */}
        <Text style={[styles.label, { color: colors.text }]}>MARKETPLACES</Text>
        {SOURCES.map((s) => {
          const active = selectedSources.includes(s);
          return (
            <View key={s} style={styles.sourceToggleRow}>
              <Text style={[styles.sourceToggleLabel, { color: colors.text }]}>{s}</Text>
              <Switch
                value={active}
                onValueChange={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); toggleSource(s); }}
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
        <View style={styles.selectGap}>
          <SelectField
            label="REGION"
            value={region}
            options={REGION_OPTIONS}
            onChange={handleRegionChange}
            placeholder="Any Region"
          />
        </View>

        {/* Status toggle (edit mode) */}
        {isEdit && (
          <View style={styles.toggleRow}>
            <Text style={[styles.label, { color: colors.muted, marginBottom: 0 }]}>ACTIVE</Text>
            <Switch
              value={status === "active"}
              onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setStatus(v ? "active" : "paused"); }}
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
                safeGoBack(router);
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
      <QuickNavBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 24 },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center" },

  title: { fontSize: 24, fontWeight: '800', marginBottom: 20, lineHeight: 30},
  // Matches SelectField's label exactly (12 / semibold / colors.text). It was
  // 11pt uppercase letter-spaced in colors.muted, so NAME and MAX PRICE read as
  // faint micro-labels while CATEGORY and MIN TRUST — rendered by SelectField —
  // were darker and larger. Two label languages alternating down one form.
  // SelectField brings no top margin, so its label sat flush against the
  // input above it. This is the same 16 the other field labels use.
  selectGap: {
    marginTop: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
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
  matchBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 11, marginTop: 6,
  },
  matchBtnText: { fontSize: 14, fontWeight: '600' },
  matchHint: { fontSize: 11, lineHeight: 15, marginTop: 6 },
  matchPicked: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 11, marginTop: 6,
  },
  matchPickedText: { flex: 1, fontSize: 14, fontWeight: '600' },
  matchList: { marginTop: 8, gap: 6 },
  matchRow: {
    borderWidth: StyleSheet.hairlineWidth, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10,
  },
  matchRowTitle: { fontSize: 14, fontWeight: '500' },
  matchRowMeta: { fontSize: 11, marginTop: 2 },
  fieldError: { fontSize: 12, marginTop: 4, marginLeft: 4 },
});
