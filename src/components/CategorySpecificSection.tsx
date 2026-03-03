/**
 * Category-specific item detail sections.
 *
 * Renders sneaker size picker, watch case size picker, LEGO details,
 * Funko vaulted badge, and sneaker authentication links depending on
 * the item's category.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { View, Text, Pressable, ActivityIndicator, StyleSheet, Linking } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { fireHaptic, HapticIntent } from "@/haptics";
import { CATEGORY_VISUAL } from "@/data/categories";
import logger from "@/utils/logger";

// Sneaker size options (US sizing)
const SNEAKER_SIZES = [
  "3.5", "4", "4.5", "5", "5.5", "6", "6.5", "7", "7.5", "8", "8.5",
  "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "14", "15",
];

// Watch case diameter options
const WATCH_SIZES = [
  "34mm", "36mm", "38mm", "39mm", "40mm", "41mm", "42mm", "43mm", "44mm", "45mm", "46mm",
];

interface CategorySpecificSectionProps {
  categorySlug: string;
  isDraft: boolean;
  itemId: string | undefined;
  itemAttributes: Record<string, unknown> | null;
  itemSizeValue: string;
  sizeSystem: "us" | "eu" | "uk" | "mm";
  sizeSaving: boolean;
  notes: string;
  hapticsEnabled: boolean;
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
  };
  onSizeChange: (size: string, system: string) => void;
  onSizeSystemChange: (system: "us" | "eu" | "uk") => void;
  onSizeValueChange: (size: string) => void;
}

export function CategorySpecificSection({
  categorySlug,
  isDraft,
  itemId,
  itemAttributes,
  itemSizeValue,
  sizeSystem,
  sizeSaving,
  notes,
  hapticsEnabled,
  theme,
  onSizeChange,
  onSizeSystemChange,
  onSizeValueChange,
}: CategorySpecificSectionProps) {
  const id = itemId;

  return (
    <>
      {/* ── Size-Specific Pricing — Sneakers ─────────────── */}
      {categorySlug === "sneakers" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="footsteps-outline" size={20} color={theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Size</Text>
            </View>
            {sizeSaving && <ActivityIndicator size="small" color={theme.accent} />}
          </View>
          <View style={s.sizeSelectorRow}>
            <View style={s.sizeSystemRow}>
              {(["US", "EU", "UK"] as const).map((sys) => (
                <Pressable
                  key={sys}
                  onPress={() => {
                    onSizeSystemChange(sys.toLowerCase() as "us" | "eu" | "uk");
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                  }}
                  style={[
                    s.sizeSystemPill,
                    {
                      backgroundColor: sizeSystem === sys.toLowerCase() ? theme.accent : theme.background,
                      borderColor: theme.border,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: sizeSystem === sys.toLowerCase() }}
                  accessibilityLabel={`Size system: ${sys}`}
                >
                  <Text
                    style={[s.sizeSystemPillText, { color: sizeSystem === sys.toLowerCase() ? "#fff" : theme.muted }]}
                  >
                    {sys}
                  </Text>
                </Pressable>
              ))}
            </View>
            <View style={s.sizePillsRow}>
              {SNEAKER_SIZES.map((sz) => (
                <Pressable
                  key={sz}
                  onPress={() => {
                    onSizeValueChange(sz);
                    onSizeChange(sz, sizeSystem);
                  }}
                  style={[
                    s.sizePill,
                    {
                      backgroundColor: itemSizeValue === sz ? theme.accent : theme.background,
                      borderColor: itemSizeValue === sz ? theme.accent : theme.border,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: itemSizeValue === sz }}
                  accessibilityLabel={`Size ${sz}`}
                >
                  <Text style={[s.sizePillText, { color: itemSizeValue === sz ? "#fff" : theme.text }]}>{sz}</Text>
                </Pressable>
              ))}
            </View>
          </View>
          <View style={[s.sizeInfoNote, { backgroundColor: theme.accent + "10" }]}>
            <Ionicons name="information-circle-outline" size={14} color={theme.accent} />
            <Text style={[s.sizeInfoNoteText, { color: theme.accent }]}>
              Size affects market value — prices vary by size
            </Text>
          </View>
        </View>
      )}

      {/* ── Size-Specific Pricing — Watches ─────────────── */}
      {categorySlug === "watches" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="watch-outline" size={20} color={theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Case Size</Text>
            </View>
            {sizeSaving && <ActivityIndicator size="small" color={theme.accent} />}
          </View>
          <View style={s.sizePillsRow}>
            {WATCH_SIZES.map((sz) => (
              <Pressable
                key={sz}
                onPress={() => {
                  onSizeValueChange(sz);
                  onSizeChange(sz, "mm");
                }}
                style={[
                  s.sizePill,
                  {
                    backgroundColor: itemSizeValue === sz ? theme.accent : theme.background,
                    borderColor: itemSizeValue === sz ? theme.accent : theme.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: itemSizeValue === sz }}
                accessibilityLabel={`Case diameter ${sz}`}
              >
                <Text style={[s.sizePillText, { color: itemSizeValue === sz ? "#fff" : theme.text }]}>{sz}</Text>
              </Pressable>
            ))}
          </View>
          <View style={[s.sizeInfoNote, { backgroundColor: theme.accent + "10" }]}>
            <Ionicons name="information-circle-outline" size={14} color={theme.accent} />
            <Text style={[s.sizeInfoNoteText, { color: theme.accent }]}>
              Size affects market value — prices vary by size
            </Text>
          </View>
        </View>
      )}

      {/* ── LEGO-Specific Features ──────────────────────── */}
      {categorySlug === "lego" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons
                name="cube-outline"
                size={20}
                color={CATEGORY_VISUAL["lego"]?.accentColor ?? theme.accent}
              />
              <Text style={[s.sectionTitle, { color: theme.text }]}>LEGO Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.piece_count || itemAttributes?.pieces) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="apps-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Piece Count</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>
                {String(itemAttributes?.piece_count || itemAttributes?.pieces)} pieces
              </Text>
            </View>
          )}
          {!!itemAttributes?.set_number && (
            <View style={s.legoDetailRow}>
              <Ionicons name="barcode-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Set</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>#{String(itemAttributes.set_number)}</Text>
            </View>
          )}
          {!!itemAttributes?.retirement_date && (
            <View style={[s.legoRetirementBadge, { backgroundColor: "#FEF3C7" }]}>
              <Ionicons name="alert-circle" size={16} color="#D97706" />
              <Text style={[s.legoRetirementText, { color: "#92400E" }]}>
                Retiring {String(itemAttributes.retirement_date)}
                {new Date(String(itemAttributes.retirement_date)) <= new Date() ? " — RETIRED" : ""}
              </Text>
            </View>
          )}
          {!!itemAttributes?.set_number && (
            <Pressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                Linking.openURL(
                  `https://www.lego.com/en-us/service/buildinginstructions/${String(itemAttributes.set_number)}`
                ).catch((err) => logger.warn("[ItemDetail] Failed to open LEGO instructions URL", err));
              }}
              style={[s.legoInstructionsBtn, { borderColor: CATEGORY_VISUAL["lego"]?.accentColor ?? theme.accent }]}
              accessibilityRole="link"
              accessibilityLabel={`Open build instructions for set ${String(itemAttributes.set_number)}`}
            >
              <Ionicons
                name="document-text-outline"
                size={16}
                color={CATEGORY_VISUAL["lego"]?.accentColor ?? theme.accent}
              />
              <Text
                style={[s.legoInstructionsBtnText, { color: CATEGORY_VISUAL["lego"]?.accentColor ?? theme.accent }]}
              >
                Build Instructions
              </Text>
              <Ionicons name="open-outline" size={14} color={CATEGORY_VISUAL["lego"]?.accentColor ?? theme.accent} />
            </Pressable>
          )}
        </View>
      )}

      {/* ── Funko Vaulted Status ─────────────────────────── */}
      {categorySlug === "funko" &&
        (itemAttributes?.vaulted === true ||
          (typeof notes === "string" && notes.toLowerCase().includes("vaulted")) ||
          (typeof itemAttributes?.notes === "string" &&
            String(itemAttributes.notes).toLowerCase().includes("vaulted"))) && (
          <View style={[s.vaultedBadgeContainer, { borderTopColor: theme.border }]}>
            <View style={[s.vaultedBadge, { backgroundColor: "#FEE2E2" }]}>
              <Ionicons name="lock-closed" size={16} color="#DC2626" />
              <Text style={[s.vaultedBadgeText, { color: "#991B1B" }]}>Vaulted</Text>
            </View>
            <Text style={[s.vaultedHint, { color: theme.muted }]}>
              This Pop! has been retired from production. Vaulted items often increase in value.
            </Text>
          </View>
        )}

      {/* ── Sneaker Authentication Links ─────────────────── */}
      {categorySlug === "sneakers" && !isDraft && id && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="shield-checkmark-outline" size={20} color="#22C55E" />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Verify Authenticity</Text>
            </View>
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, paddingTop: 8 }}>
            <Pressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                Linking.openURL("https://checkcheck.com").catch((err) =>
                  logger.warn("[ItemDetail] Failed to open CheckCheck URL", err)
                );
              }}
              style={[s.authLinkBtn, { borderColor: "#22C55E" }]}
              accessibilityRole="link"
              accessibilityLabel="Verify with CheckCheck"
            >
              <Ionicons name="checkmark-circle-outline" size={16} color="#22C55E" />
              <Text style={[s.authLinkBtnText, { color: "#22C55E" }]}>CheckCheck</Text>
              <Ionicons name="open-outline" size={12} color="#22C55E" />
            </Pressable>
            <Pressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                Linking.openURL("https://www.legitcheck.app").catch((err) =>
                  logger.warn("[ItemDetail] Failed to open Legit Check URL", err)
                );
              }}
              style={[s.authLinkBtn, { borderColor: "#3B82F6" }]}
              accessibilityRole="link"
              accessibilityLabel="Verify with Legit Check"
            >
              <Ionicons name="shield-checkmark-outline" size={16} color="#3B82F6" />
              <Text style={[s.authLinkBtnText, { color: "#3B82F6" }]}>Legit Check</Text>
              <Ionicons name="open-outline" size={12} color="#3B82F6" />
            </Pressable>
          </View>
        </View>
      )}
    </>
  );
}

const s = StyleSheet.create({
  sectionBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingBottom: 4,
  },
  sectionHeaderLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "700" },
  sizeSelectorRow: { paddingTop: 8 },
  sizeSystemRow: { flexDirection: "row", gap: 8, marginBottom: 10 },
  sizeSystemPill: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 16, borderWidth: 1 },
  sizeSystemPillText: { fontSize: 13, fontWeight: "600" },
  sizePillsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  sizePill: { minWidth: 44, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 10, borderWidth: 1, alignItems: "center" },
  sizePillText: { fontSize: 13, fontWeight: "600" },
  sizeInfoNote: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, marginTop: 10 },
  sizeInfoNoteText: { fontSize: 12, fontWeight: "500", flex: 1 },
  legoDetailRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
  legoDetailLabel: { fontSize: 13, fontWeight: "500", flex: 1 },
  legoDetailValue: { fontSize: 13, fontWeight: "700" },
  legoRetirementBadge: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, marginTop: 6 },
  legoRetirementText: { fontSize: 13, fontWeight: "600", flex: 1 },
  legoInstructionsBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, paddingVertical: 10, borderRadius: 10, borderWidth: 1, marginTop: 8 },
  legoInstructionsBtnText: { fontSize: 13, fontWeight: "600" },
  vaultedBadgeContainer: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  vaultedBadge: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, marginBottom: 6 },
  vaultedBadgeText: { fontSize: 14, fontWeight: "700" },
  vaultedHint: { fontSize: 12, lineHeight: 17 },
  authLinkBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1 },
  authLinkBtnText: { fontSize: 13, fontWeight: "600" },
});
