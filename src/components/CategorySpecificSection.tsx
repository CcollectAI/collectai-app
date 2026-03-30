/**
 * Category-specific item detail sections.
 *
 * Renders category-aware UI panels depending on the item's category:
 * sneakers (size picker + auth links), watches (case size picker),
 * LEGO (piece count, set number, retirement, build instructions),
 * Funko (vaulted badge), comic_books (grade, key issue, signed, CGC lookup),
 * vinyl_records (pressing, RPM, color vinyl, Discogs link),
 * warhammer (faction, game system, community link),
 * whiskey (distillery, expression, age, sealed),
 * vintage_cameras (film format, camera type, working status),
 * blind_box (brand, series, chase/secret, sealed),
 * pens (nib size/material, filling system, limited edition).
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { View, Text, Pressable, ActivityIndicator, StyleSheet, Linking } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { fireHaptic, HapticIntent } from "@/haptics";
import { CATEGORY_VISUAL } from "@/data/categories";
import { useAppTheme } from "@/theme/useAppTheme";
import { useSettings } from "@/lib/settings";
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
  onSizeChange: (size: string, system: string) => void;
  onSizeSystemChange: (system: "us" | "eu" | "uk") => void;
  onSizeValueChange: (size: string) => void;
}

function CategorySpecificSectionInner({
  categorySlug,
  isDraft,
  itemId,
  itemAttributes,
  itemSizeValue,
  sizeSystem,
  sizeSaving,
  notes,
  onSizeChange,
  onSizeSystemChange,
  onSizeValueChange,
}: CategorySpecificSectionProps) {
  const id = itemId;
  const { colors, isDark } = useAppTheme();
  const { settings } = useSettings();
  const hapticsEnabled = settings.hapticsEnabled;
  const theme = colors;
  const catVisual = CATEGORY_VISUAL[categorySlug as keyof typeof CATEGORY_VISUAL];
  const catAccent = catVisual?.accentColor ?? theme.accent;

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
            <View style={[s.legoRetirementBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="alert-circle" size={16} color={colors.warning} />
              <Text style={[s.legoRetirementText, { color: colors.warning }]}>
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
            <View style={[s.vaultedBadge, { backgroundColor: colors.dangerBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.danger} />
              <Text style={[s.vaultedBadgeText, { color: colors.danger }]}>Vaulted</Text>
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
              <Ionicons name="shield-checkmark-outline" size={20} color={colors.success} />
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
              style={[s.authLinkBtn, { borderColor: colors.success }]}
              accessibilityRole="link"
              accessibilityLabel="Verify with CheckCheck"
            >
              <Ionicons name="checkmark-circle-outline" size={16} color={colors.success} />
              <Text style={[s.authLinkBtnText, { color: colors.success }]}>CheckCheck</Text>
              <Ionicons name="open-outline" size={12} color={colors.success} />
            </Pressable>
            <Pressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                Linking.openURL("https://www.legitcheck.app").catch((err) =>
                  logger.warn("[ItemDetail] Failed to open Legit Check URL", err)
                );
              }}
              style={[s.authLinkBtn, { borderColor: colors.info }]}
              accessibilityRole="link"
              accessibilityLabel="Verify with Legit Check"
            >
              <Ionicons name="shield-checkmark-outline" size={16} color={colors.info} />
              <Text style={[s.authLinkBtnText, { color: colors.info }]}>Legit Check</Text>
              <Ionicons name="open-outline" size={12} color={colors.info} />
            </Pressable>
          </View>
        </View>
      )}

      {/* ── Comic Books ─────────────────────────────────── */}
      {categorySlug === "comic_books" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="book-outline" size={20} color={CATEGORY_VISUAL["comic_books"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Comic Details</Text>
            </View>
          </View>
          {!!itemAttributes?.grade && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shield-checkmark-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Grade</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.grade)}</Text>
            </View>
          )}
          {itemAttributes?.key_issue === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Key Issue</Text>
            </View>
          )}
          {itemAttributes?.signed === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="create" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>Signed</Text>
            </View>
          )}
          {!!itemAttributes?.grade && (
            <Pressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                Linking.openURL("https://www.cgccomics.com/certlookup").catch((err) =>
                  logger.warn("[ItemDetail] Failed to open CGC URL", err)
                );
              }}
              style={[s.legoInstructionsBtn, { borderColor: CATEGORY_VISUAL["comic_books"]?.accentColor ?? theme.accent }]}
              accessibilityRole="link"
              accessibilityLabel="Look up CGC certificate"
            >
              <Ionicons name="search-outline" size={16} color={CATEGORY_VISUAL["comic_books"]?.accentColor ?? theme.accent} />
              <Text style={[s.legoInstructionsBtnText, { color: CATEGORY_VISUAL["comic_books"]?.accentColor ?? theme.accent }]}>
                CGC Cert Lookup
              </Text>
              <Ionicons name="open-outline" size={14} color={CATEGORY_VISUAL["comic_books"]?.accentColor ?? theme.accent} />
            </Pressable>
          )}
        </View>
      )}

      {/* ── Vinyl Records ───────────────────────────────── */}
      {categorySlug === "vinyl_records" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="disc-outline" size={20} color={CATEGORY_VISUAL["vinyl_records"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Vinyl Details</Text>
            </View>
          </View>
          {!!itemAttributes?.pressing && (
            <View style={s.legoDetailRow}>
              <Ionicons name="layers-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Pressing</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.pressing)}</Text>
            </View>
          )}
          {!!itemAttributes?.rpm && (
            <View style={s.legoDetailRow}>
              <Ionicons name="speedometer-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>RPM</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.rpm)}</Text>
            </View>
          )}
          {itemAttributes?.color_vinyl === true && (
            <View style={[s.vaultedBadge, { backgroundColor: isDark ? '#3B1F6E' : '#F3E8FF' }]}>
              <Ionicons name="color-palette" size={16} color={isDark ? '#C4B5FD' : '#7C3AED'} />
              <Text style={[s.vaultedBadgeText, { color: isDark ? '#C4B5FD' : '#5B21B6' }]}>Color Vinyl</Text>
            </View>
          )}
          <Pressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              Linking.openURL("https://www.discogs.com").catch((err) =>
                logger.warn("[ItemDetail] Failed to open Discogs URL", err)
              );
            }}
            style={[s.legoInstructionsBtn, { borderColor: CATEGORY_VISUAL["vinyl_records"]?.accentColor ?? theme.accent }]}
            accessibilityRole="link"
            accessibilityLabel="Browse on Discogs"
          >
            <Ionicons name="disc-outline" size={16} color={CATEGORY_VISUAL["vinyl_records"]?.accentColor ?? theme.accent} />
            <Text style={[s.legoInstructionsBtnText, { color: CATEGORY_VISUAL["vinyl_records"]?.accentColor ?? theme.accent }]}>
              Discogs
            </Text>
            <Ionicons name="open-outline" size={14} color={CATEGORY_VISUAL["vinyl_records"]?.accentColor ?? theme.accent} />
          </Pressable>
        </View>
      )}

      {/* ── Warhammer ───────────────────────────────────── */}
      {categorySlug === "warhammer" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="skull-outline" size={20} color={CATEGORY_VISUAL["warhammer"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Warhammer Details</Text>
            </View>
          </View>
          {!!itemAttributes?.faction && (
            <View style={s.legoDetailRow}>
              <Ionicons name="flag-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Faction</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.faction)}</Text>
            </View>
          )}
          {!!itemAttributes?.game_system && (
            <View style={s.legoDetailRow}>
              <Ionicons name="game-controller-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Game System</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.game_system)}</Text>
            </View>
          )}
          <Pressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              Linking.openURL("https://www.warhammer-community.com").catch((err) =>
                logger.warn("[ItemDetail] Failed to open Warhammer Community URL", err)
              );
            }}
            style={[s.legoInstructionsBtn, { borderColor: CATEGORY_VISUAL["warhammer"]?.accentColor ?? theme.accent }]}
            accessibilityRole="link"
            accessibilityLabel="Visit Warhammer Community"
          >
            <Ionicons name="globe-outline" size={16} color={CATEGORY_VISUAL["warhammer"]?.accentColor ?? theme.accent} />
            <Text style={[s.legoInstructionsBtnText, { color: CATEGORY_VISUAL["warhammer"]?.accentColor ?? theme.accent }]}>
              Warhammer Community
            </Text>
            <Ionicons name="open-outline" size={14} color={CATEGORY_VISUAL["warhammer"]?.accentColor ?? theme.accent} />
          </Pressable>
        </View>
      )}

      {/* ── Whiskey ──────────────────────────────────────── */}
      {categorySlug === "whiskey" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="wine-outline" size={20} color={CATEGORY_VISUAL["whiskey"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Whiskey Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.brand || itemAttributes?.distillery) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Distillery</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>
                {String(itemAttributes?.distillery || itemAttributes?.brand)}
              </Text>
            </View>
          )}
          {!!itemAttributes?.expression && (
            <View style={s.legoDetailRow}>
              <Ionicons name="flask-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Expression</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.expression)}</Text>
            </View>
          )}
          {!!itemAttributes?.age_statement && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="time" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>
                {String(itemAttributes.age_statement)} Year
              </Text>
            </View>
          )}
          {itemAttributes?.sealed === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Sealed</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Vintage Cameras ─────────────────────────────── */}
      {categorySlug === "vintage_cameras" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="camera-outline" size={20} color={CATEGORY_VISUAL["vintage_cameras"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Camera Details</Text>
            </View>
          </View>
          {!!itemAttributes?.film_format && (
            <View style={s.legoDetailRow}>
              <Ionicons name="film-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Film Format</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.film_format)}</Text>
            </View>
          )}
          {!!itemAttributes?.camera_type && (
            <View style={s.legoDetailRow}>
              <Ionicons name="aperture-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Camera Type</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.camera_type)}</Text>
            </View>
          )}
          {itemAttributes?.working === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Working</Text>
            </View>
          )}
          {itemAttributes?.working === false && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.dangerBg }]}>
              <Ionicons name="close-circle" size={16} color={colors.danger} />
              <Text style={[s.vaultedBadgeText, { color: colors.danger }]}>Not Working</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Blind Box ───────────────────────────────────── */}
      {categorySlug === "blind_box" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="gift-outline" size={20} color={CATEGORY_VISUAL["blind_box"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Blind Box Details</Text>
            </View>
          </View>
          {!!itemAttributes?.brand && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Brand</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.brand)}</Text>
            </View>
          )}
          {!!itemAttributes?.series && (
            <View style={s.legoDetailRow}>
              <Ionicons name="albums-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Series</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.series)}</Text>
            </View>
          )}
          {(itemAttributes?.chase === true || itemAttributes?.secret === true) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>
                {itemAttributes?.secret ? "Secret" : "Chase"}
              </Text>
            </View>
          )}
          {itemAttributes?.sealed === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Sealed</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pens ────────────────────────────────────────── */}
      {categorySlug === "pens" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="create-outline" size={20} color={CATEGORY_VISUAL["pens"]?.accentColor ?? theme.accent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Pen Details</Text>
            </View>
          </View>
          {!!itemAttributes?.nib_size && (
            <View style={s.legoDetailRow}>
              <Ionicons name="create-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Nib Size</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.nib_size)}</Text>
            </View>
          )}
          {!!itemAttributes?.nib_material && (
            <View style={s.legoDetailRow}>
              <Ionicons name="diamond-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Nib Material</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.nib_material)}</Text>
            </View>
          )}
          {!!itemAttributes?.filling_system && (
            <View style={s.legoDetailRow}>
              <Ionicons name="water-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Filling System</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.filling_system)}</Text>
            </View>
          )}
          {itemAttributes?.limited_edition === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Limited Edition</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: TCG — pokemon, mtg, yugioh, lorcana, digimon, one_piece_tcg ── */}
      {["pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="albums-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Card Details</Text>
            </View>
          </View>
          {!!itemAttributes?.set && (
            <View style={s.legoDetailRow}>
              <Ionicons name="albums-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Set</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.set)}</Text>
            </View>
          )}
          {!!(itemAttributes?.number || itemAttributes?.collector_no) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="barcode-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Number</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.number || itemAttributes?.collector_no)}</Text>
            </View>
          )}
          {!!itemAttributes?.rarity && (
            <View style={s.legoDetailRow}>
              <Ionicons name="star-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Rarity</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.rarity)}</Text>
            </View>
          )}
          {(itemAttributes?.foil === true || itemAttributes?.variant === "Foil" || itemAttributes?.variant === "foil") && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="sparkles" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Foil / Holo</Text>
            </View>
          )}
          {(itemAttributes?.edition === "1st Edition" || itemAttributes?.printing === "1st Edition") && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="ribbon" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>1st Edition</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Figure — anime_figures, hot_toys, designer_toys, bandai_premium, action_figures, marvel_legends ── */}
      {["anime_figures", "designer_toys", "bandai_premium", "action_figures", "marvel_legends"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="body-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Figure Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.manufacturer || itemAttributes?.brand || itemAttributes?.line) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Manufacturer</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.manufacturer || itemAttributes?.brand || itemAttributes?.line)}</Text>
            </View>
          )}
          {!!(itemAttributes?.franchise || itemAttributes?.series) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="film-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Franchise</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.franchise || itemAttributes?.series)}</Text>
            </View>
          )}
          {!!itemAttributes?.scale && (
            <View style={s.legoDetailRow}>
              <Ionicons name="resize-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Scale</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.scale)}</Text>
            </View>
          )}
          {!!itemAttributes?.character && (
            <View style={s.legoDetailRow}>
              <Ionicons name="person-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Character</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.character)}</Text>
            </View>
          )}
          {!!itemAttributes?.baf_figure && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="construct" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>BAF: {String(itemAttributes.baf_figure)}</Text>
            </View>
          )}
          {(itemAttributes?.limited_edition === true || itemAttributes?.edition === "Limited" || itemAttributes?.p_bandai === true || !!itemAttributes?.retailer_exclusive) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>
                {itemAttributes?.retailer_exclusive ? String(itemAttributes.retailer_exclusive) + " Exclusive" : "Limited / Exclusive"}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Legacy — vintage_toys, diecast, retro_handhelds, retro_games, sportscards ── */}
      {["vintage_toys", "retro_handhelds"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="time-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Item Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.era || itemAttributes?.year) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="time-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Era</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.era || itemAttributes?.year)}</Text>
            </View>
          )}
          {!!(itemAttributes?.manufacturer || itemAttributes?.brand || itemAttributes?.console_type) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Manufacturer</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.manufacturer || itemAttributes?.brand || itemAttributes?.console_type)}</Text>
            </View>
          )}
          {!!(itemAttributes?.completeness || itemAttributes?.boxed) && (
            <View style={[s.vaultedBadge, { backgroundColor: itemAttributes?.completeness === "CIB" || itemAttributes?.boxed === true ? colors.successBg : colors.warningBg }]}>
              <Ionicons name="checkmark-done" size={16} color={itemAttributes?.completeness === "CIB" || itemAttributes?.boxed === true ? colors.success : colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: itemAttributes?.completeness === "CIB" || itemAttributes?.boxed === true ? colors.success : colors.warning }]}>
                {itemAttributes?.completeness ? String(itemAttributes.completeness) : (itemAttributes?.boxed ? "Boxed" : "Loose")}
              </Text>
            </View>
          )}
          {!!itemAttributes?.afa_grade && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="shield-checkmark" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>{String(itemAttributes.afa_grade)}</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Building — gunpla, scale_models ──────────── */}
      {["gunpla", "scale_models"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="construct-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Kit Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.grade || itemAttributes?.subject) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="layers-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>{categorySlug === "gunpla" ? "Grade" : "Subject"}</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.grade || itemAttributes?.subject)}</Text>
            </View>
          )}
          {!!itemAttributes?.scale && (
            <View style={s.legoDetailRow}>
              <Ionicons name="resize-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Scale</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.scale)}</Text>
            </View>
          )}
          {!!(itemAttributes?.brand || itemAttributes?.series) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Brand / Series</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.brand || itemAttributes?.series)}</Text>
            </View>
          )}
          {itemAttributes?.built === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Built</Text>
            </View>
          )}
          {itemAttributes?.built === false && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="cube" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>Unbuilt</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Music & Fandom — kpop_merch, taylor_swift, pop_fandom, kpop_lightsticks ── */}
      {["kpop_merch", "taylor_swift", "pop_fandom", "kpop_lightsticks"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="musical-notes-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Merch Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.artist || itemAttributes?.vtuber) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="person-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Artist / Group</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.artist || itemAttributes?.vtuber)}</Text>
            </View>
          )}
          {!!(itemAttributes?.album || itemAttributes?.tour || itemAttributes?.era) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="disc-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Album / Tour</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.album || itemAttributes?.tour || itemAttributes?.era)}</Text>
            </View>
          )}
          {!!itemAttributes?.item_type && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shapes-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Type</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.item_type)}</Text>
            </View>
          )}
          {itemAttributes?.signed === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.infoBg }]}>
              <Ionicons name="create" size={16} color={colors.info} />
              <Text style={[s.vaultedBadgeText, { color: colors.info }]}>Signed</Text>
            </View>
          )}
          {!!(itemAttributes?.member) && (
            <View style={[s.vaultedBadge, { backgroundColor: "#F3E8FF" }]}>
              <Ionicons name="person" size={16} color="#7C3AED" />
              <Text style={[s.vaultedBadgeText, { color: "#5B21B6" }]}>{String(itemAttributes.member)}</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Media — manga, bluray_steelbook, anime_bluray, anime_soundtrack, anime_ost_vinyl ── */}
      {["manga", "bluray_steelbook", "anime_bluray", "anime_soundtrack", "anime_ost_vinyl"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="film-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Media Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.studio || itemAttributes?.publisher || itemAttributes?.label) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Studio / Publisher</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.studio || itemAttributes?.publisher || itemAttributes?.label)}</Text>
            </View>
          )}
          {!!(itemAttributes?.format || itemAttributes?.volume) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="layers-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Format</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.format || (itemAttributes?.volume ? `Vol. ${itemAttributes.volume}` : ""))}</Text>
            </View>
          )}
          {!!itemAttributes?.region && (
            <View style={s.legoDetailRow}>
              <Ionicons name="globe-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Region</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.region)}</Text>
            </View>
          )}
          {(itemAttributes?.sealed === true) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Sealed</Text>
            </View>
          )}
          {(itemAttributes?.limited === true || itemAttributes?.edition === "limited") && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Limited Edition</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Disney & Parks — disney, theme_park, ghibli ── */}
      {["disney", "theme_park", "ghibli"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="planet-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Disney Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.franchise || itemAttributes?.film) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="film-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Franchise / Film</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.franchise || itemAttributes?.film)}</Text>
            </View>
          )}
          {!!(itemAttributes?.park || itemAttributes?.collection) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="location-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Park / Collection</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.park || itemAttributes?.collection)}</Text>
            </View>
          )}
          {!!itemAttributes?.year && (
            <View style={s.legoDetailRow}>
              <Ionicons name="calendar-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Year</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.year)}</Text>
            </View>
          )}
          {(itemAttributes?.park_exclusive === true || itemAttributes?.limited_edition === true || itemAttributes?.jp_exclusive === true) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>
                {itemAttributes?.park_exclusive ? "Park Exclusive" : itemAttributes?.jp_exclusive ? "JP Exclusive" : "Limited Edition"}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Japan — jp_magazine, jp_event ──────────── */}
      {["jp_magazine", "jp_event"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="newspaper-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Japan Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.magazine || itemAttributes?.event) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="document-text-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Publication / Event</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.magazine || itemAttributes?.event)}</Text>
            </View>
          )}
          {!!itemAttributes?.franchise && (
            <View style={s.legoDetailRow}>
              <Ionicons name="film-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Franchise</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.franchise)}</Text>
            </View>
          )}
          {!!(itemAttributes?.issue || itemAttributes?.season) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="calendar-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Issue / Date</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.issue || itemAttributes?.season)}</Text>
            </View>
          )}
          {itemAttributes?.limited_quantity === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.dangerBg }]}>
              <Ionicons name="alert-circle" size={16} color={colors.danger} />
              <Text style={[s.vaultedBadgeText, { color: colors.danger }]}>Limited Quantity</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Nintendo — nintendo_merch, retro_pokemon ── */}
      {["nintendo_merch", "retro_pokemon"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="game-controller-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Nintendo Details</Text>
            </View>
          </View>
          {!!itemAttributes?.franchise && (
            <View style={s.legoDetailRow}>
              <Ionicons name="star-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Franchise</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.franchise)}</Text>
            </View>
          )}
          {!!(itemAttributes?.item_type || itemAttributes?.generation) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shapes-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>{itemAttributes?.generation ? "Generation" : "Type"}</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.generation || itemAttributes?.item_type)}</Text>
            </View>
          )}
          {!!itemAttributes?.region && (
            <View style={s.legoDetailRow}>
              <Ionicons name="globe-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Region</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.region)}</Text>
            </View>
          )}
          {!!(itemAttributes?.store_exclusive) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.dangerBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.danger} />
              <Text style={[s.vaultedBadgeText, { color: colors.danger }]}>{String(itemAttributes.store_exclusive)} Exclusive</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: IP-Specific — one_piece, vtuber ─────── */}
      {["one_piece", "vtuber"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="star-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.character || itemAttributes?.vtuber) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="person-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Character</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.character || itemAttributes?.vtuber)}</Text>
            </View>
          )}
          {!!(itemAttributes?.line || itemAttributes?.event) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="albums-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Line / Event</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.line || itemAttributes?.event)}</Text>
            </View>
          )}
          {!!itemAttributes?.item_type && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shapes-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Type</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.item_type)}</Text>
            </View>
          )}
          {itemAttributes?.official === false && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="alert-circle" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Unofficial</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Niche — keycaps, loungefly, plush_collectibles ── */}
      {["keycaps", "loungefly", "plush_collectibles"].includes(categorySlug) && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="diamond-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Details</Text>
            </View>
          </View>
          {!!(itemAttributes?.maker || itemAttributes?.brand || itemAttributes?.license) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Brand</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.maker || itemAttributes?.brand || itemAttributes?.license)}</Text>
            </View>
          )}
          {!!(itemAttributes?.sculpt || itemAttributes?.character || itemAttributes?.collection) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shapes-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>
                {itemAttributes?.sculpt ? "Sculpt" : itemAttributes?.character ? "Character" : "Collection"}
              </Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.sculpt || itemAttributes?.character || itemAttributes?.collection)}</Text>
            </View>
          )}
          {!!(itemAttributes?.profile || itemAttributes?.size || itemAttributes?.material) && (
            <View style={s.legoDetailRow}>
              <Ionicons name="resize-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>
                {itemAttributes?.profile ? "Profile" : itemAttributes?.size ? "Size" : "Material"}
              </Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes?.profile || itemAttributes?.size || itemAttributes?.material)}</Text>
            </View>
          )}
          {(itemAttributes?.has_tags === true) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="pricetag" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>Has Tags</Text>
            </View>
          )}
          {!!(itemAttributes?.exclusive_retailer || itemAttributes?.retailer) && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="lock-closed" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>{String(itemAttributes?.exclusive_retailer || itemAttributes?.retailer)} Exclusive</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Sportscards ──────────────────────────── */}
      {categorySlug === "sportscards" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="trophy-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Card Details</Text>
            </View>
          </View>
          {!!itemAttributes?.player && (
            <View style={s.legoDetailRow}>
              <Ionicons name="person-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Player</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.player)}</Text>
            </View>
          )}
          {!!itemAttributes?.set && (
            <View style={s.legoDetailRow}>
              <Ionicons name="albums-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Set</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.set)}</Text>
            </View>
          )}
          {!!itemAttributes?.grade && (
            <View style={s.legoDetailRow}>
              <Ionicons name="shield-checkmark-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Grade</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.grade)}</Text>
            </View>
          )}
          {!!itemAttributes?.variant && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="sparkles" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>{String(itemAttributes.variant)}</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Retro Games (standalone) ────────────── */}
      {categorySlug === "retro_games" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="game-controller-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Game Details</Text>
            </View>
          </View>
          {!!itemAttributes?.platform && (
            <View style={s.legoDetailRow}>
              <Ionicons name="hardware-chip-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Platform</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.platform)}</Text>
            </View>
          )}
          {!!itemAttributes?.title && (
            <View style={s.legoDetailRow}>
              <Ionicons name="text-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Title</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.title)}</Text>
            </View>
          )}
          {!!itemAttributes?.completeness && (
            <View style={[s.vaultedBadge, { backgroundColor: itemAttributes.completeness === "sealed" ? colors.successBg : colors.warningBg }]}>
              <Ionicons name="checkmark-done" size={16} color={itemAttributes.completeness === "sealed" ? colors.success : colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: itemAttributes.completeness === "sealed" ? colors.success : colors.warning }]}>
                {String(itemAttributes.completeness).toUpperCase()}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: OOP Board Games ────────────────── */}
      {categorySlug === "oop_board_games" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="dice-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Board Game Details</Text>
            </View>
          </View>
          {!!itemAttributes?.publisher && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Publisher</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.publisher)}</Text>
            </View>
          )}
          {!!itemAttributes?.designer && (
            <View style={s.legoDetailRow}>
              <Ionicons name="person-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Designer</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.designer)}</Text>
            </View>
          )}
          {!!itemAttributes?.player_count && (
            <View style={s.legoDetailRow}>
              <Ionicons name="people-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Players</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.player_count)}</Text>
            </View>
          )}
          {!!itemAttributes?.edition && (
            <View style={s.legoDetailRow}>
              <Ionicons name="ribbon-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Edition</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.edition)}</Text>
            </View>
          )}
          {!!itemAttributes?.bgg_rating && (
            <View style={s.legoDetailRow}>
              <Ionicons name="star-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>BGG Rating</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.bgg_rating)}</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: City Pop Vinyl ────────────────── */}
      {categorySlug === "city_pop_vinyl" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="musical-note-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>City Pop Vinyl Details</Text>
            </View>
          </View>
          {!!itemAttributes?.artist && (
            <View style={s.legoDetailRow}>
              <Ionicons name="mic-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Artist</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.artist)}</Text>
            </View>
          )}
          {!!itemAttributes?.album && (
            <View style={s.legoDetailRow}>
              <Ionicons name="disc-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Album</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.album)}</Text>
            </View>
          )}
          {!!itemAttributes?.label && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Label</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.label)}</Text>
            </View>
          )}
          {!!itemAttributes?.pressing && (
            <View style={s.legoDetailRow}>
              <Ionicons name="albums-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Pressing</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.pressing)}</Text>
            </View>
          )}
          {itemAttributes?.obi === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.successBg }]}>
              <Ionicons name="bookmark" size={16} color={colors.success} />
              <Text style={[s.vaultedBadgeText, { color: colors.success }]}>OBI Strip Included</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Fragrances (inventory tracking focus) ────────────────── */}
      {categorySlug === "fragrances" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="rose-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Fragrance Details</Text>
            </View>
          </View>
          {!!itemAttributes?.house && (
            <View style={s.legoDetailRow}>
              <Ionicons name="business-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>House</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.house)}</Text>
            </View>
          )}
          {!!itemAttributes?.fragrance_name && (
            <View style={s.legoDetailRow}>
              <Ionicons name="water-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Fragrance</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.fragrance_name)}</Text>
            </View>
          )}
          {!!itemAttributes?.concentration && (
            <View style={s.legoDetailRow}>
              <Ionicons name="flask-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Concentration</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.concentration)}</Text>
            </View>
          )}
          {!!itemAttributes?.size_ml && (
            <View style={s.legoDetailRow}>
              <Ionicons name="resize-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Size</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.size_ml)}ml</Text>
            </View>
          )}
          {!!itemAttributes?.fragrance_family && (
            <View style={s.legoDetailRow}>
              <Ionicons name="leaf-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Family</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.fragrance_family)}</Text>
            </View>
          )}
          {!!itemAttributes?.fill_level && (
            <View style={s.legoDetailRow}>
              <Ionicons name="beaker-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Fill Level</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.fill_level)}</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Pattern: Diecast (standalone) ────────────────── */}
      {categorySlug === "diecast" && (
        <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
          <View style={s.sectionHeaderRow}>
            <View style={s.sectionHeaderLeft}>
              <Ionicons name="speedometer-outline" size={20} color={catAccent} />
              <Text style={[s.sectionTitle, { color: theme.text }]}>Diecast Details</Text>
            </View>
          </View>
          {!!itemAttributes?.brand && (
            <View style={s.legoDetailRow}>
              <Ionicons name="car-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Brand</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.brand)}</Text>
            </View>
          )}
          {!!itemAttributes?.scale && (
            <View style={s.legoDetailRow}>
              <Ionicons name="resize-outline" size={16} color={theme.muted} />
              <Text style={[s.legoDetailLabel, { color: theme.muted }]}>Scale</Text>
              <Text style={[s.legoDetailValue, { color: theme.text }]}>{String(itemAttributes.scale)}</Text>
            </View>
          )}
          {itemAttributes?.chase === true && (
            <View style={[s.vaultedBadge, { backgroundColor: colors.warningBg }]}>
              <Ionicons name="star" size={16} color={colors.warning} />
              <Text style={[s.vaultedBadgeText, { color: colors.warning }]}>Chase / Treasure Hunt</Text>
            </View>
          )}
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

export const CategorySpecificSection = React.memo(CategorySpecificSectionInner);
