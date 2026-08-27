/**
 * Dossier / Full Report section for item detail screen.
 *
 * Renders a collapsible "Full Report" header with error state and retry,
 * valuation summary card, market comps count, authenticity signals,
 * and an export button.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from "react-native";
// `/legacy`, matching app/(tabs)/items.tsx: the package's main entry no
// longer exports `documentDirectory`, and tsc says so.
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { collectorsApi } from "@/api/collectorsApi";
import logger from "@/utils/logger";

// ── Exported types ──────────────────────────────────────────────────────

export interface DossierData {
  item_id: string;
  generated_at: string;
  identity: Record<string, unknown>;
  valuation: Record<string, unknown>;
  provenance: Record<string, unknown>[];
  price_history: Record<string, unknown>[];
  market_comps: Record<string, unknown>[];
  photos: string[];
  collections: string[];
  authenticity_signals: string[];
  completeness_score: number;
}

// ── Props interface ─────────────────────────────────────────────────────

interface DossierReportSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
  };
  dossierData: DossierData | null;
  dossierLoading: boolean;
  dossierExpanded: boolean;
  dossierError: boolean;
  onToggleExpanded: () => void;
  onRetry: () => void;
  itemId: string;
  formatPrice: (value: number | undefined, currency?: string) => string;
  toNum: (value: string | number | undefined | null) => number | undefined;
}

// ── Component ───────────────────────────────────────────────────────────

export const DossierReportSection = React.memo(function DossierReportSection({
  theme,
  dossierData,
  dossierLoading,
  dossierExpanded,
  dossierError,
  onToggleExpanded,
  onRetry,
  itemId,
  formatPrice,
  toNum,
}: DossierReportSectionProps) {
  const [exporting, setExporting] = useState(false);
  const { t } = useTranslation();
  return (
    <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
      <Pressable
        onPress={onToggleExpanded}
        style={s.sectionHeaderRow}
        accessibilityRole="button"
        accessibilityLabel={`Valuation report, ${dossierExpanded ? 'expanded' : 'collapsed'}`}
      >
        <View style={s.sectionHeaderLeft}>
          <Ionicons name="document-text-outline" size={20} color={theme.accent} />
          <Text style={[s.sectionTitle, { color: theme.text }]}>{t('dossier.valuation_report')}</Text>
        </View>
        {dossierLoading ? (
          <ActivityIndicator size="small" color={theme.accent} />
        ) : (
          <Ionicons
            name={dossierExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.muted}
          />
        )}
      </Pressable>
      {dossierExpanded && dossierError && !dossierData && (
        <View style={s.sectionContent}>
          <Text style={[s.emptyText, { color: theme.muted }]}>
            Could not load report. Check your connection and try again.
          </Text>
          <AnimatedPressable
            onPress={onRetry}
            style={[s.retryBtn, { borderColor: theme.accent }]}
            accessibilityRole="button"
            accessibilityLabel={t('dossier.retry_a11y')}
          >
            <Text style={{ color: theme.accent, fontSize: 13, fontWeight: "600" }}>Retry</Text>
          </AnimatedPressable>
        </View>
      )}
      {dossierExpanded && dossierData && (
        <View style={s.sectionContent}>
          {/* Valuation summary */}
          {dossierData.valuation?.q50 != null && (
            <View style={[s.dossierCard, { backgroundColor: theme.background }]}>
              <Text style={[s.dossierLabel, { color: theme.muted }]}>{t('dossier.estimated_value')}</Text>
              <Text style={[s.dossierValue, { color: theme.text }]}>
                {formatPrice(toNum(dossierData.valuation.q50 as string | number))}
              </Text>
              {typeof dossierData.valuation.explanation === 'string' && (
                <Text style={[s.dossierMeta, { color: theme.muted }]}>
                  {dossierData.valuation.explanation}
                </Text>
              )}
            </View>
          )}
          {/* Market comps count */}
          {dossierData.market_comps?.length > 0 && (
            <View style={s.dossierRow}>
              <Text style={[s.dossierRowLabel, { color: theme.muted }]}>{t('dossier.similar_listings')}</Text>
              <Text style={[s.dossierRowValue, { color: theme.text }]}>
                {dossierData.market_comps.length} found
              </Text>
            </View>
          )}
          {/* Authenticity signals */}
          {dossierData.authenticity_signals?.length > 0 && (
            <View style={s.dossierRow}>
              <Text style={[s.dossierRowLabel, { color: theme.muted }]}>Authenticity</Text>
              <Text style={[s.dossierRowValue, { color: theme.accent }]}>
                {dossierData.authenticity_signals.join(", ").replace(/_/g, " ")}
              </Text>
            </View>
          )}
          {/* Export button */}
          {/* FETCH, then share — do not open the URL.
              `/dossier/{id}/export` is `Depends(get_current_user_id)` +
              `require_plan("pro")`, and `Linking.openURL` hands it to the
              system browser, which has no session. A Pro member tapping this
              left the app and landed on a white page reading
              `{"detail":"Authentication required"}` — a sold feature, on the
              tier that pays for it, that had never worked.
              Same shape as every other authed-URL bug in this repo: an address
              built for our API given to something that cannot authenticate. */}
          <Pressable
            disabled={exporting}
            onPress={async () => {
              if (exporting) return;
              setExporting(true);
              try {
                const html = await collectorsApi.fetchDossierExportHtml(itemId);
                const filename = `Sparrow Collect_Report_${itemId.slice(0, 8)}.html`;
                if (!FileSystem.documentDirectory) {
                  throw new Error("File storage not available on this platform");
                }
                const filePath = `${FileSystem.documentDirectory}${filename}`;
                await FileSystem.writeAsStringAsync(filePath, html);
                if (await Sharing.isAvailableAsync()) {
                  await Sharing.shareAsync(filePath, {
                    mimeType: "text/html",
                    dialogTitle: "Export Report",
                    UTI: "public.html",
                  });
                } else {
                  // Saved but not shareable is still a result, and saying so
                  // beats a button that appears to do nothing.
                  Alert.alert("Report saved", `Saved as ${filename}`);
                }
              } catch (err) {
                logger.error("[ItemDetail] dossier export failed:", err);
                Alert.alert(
                  "Export failed",
                  (err as Error)?.message || "Could not build the report. Please try again.",
                );
              } finally {
                setExporting(false);
              }
            }}
            style={[s.dossierExportBtn, { borderColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={t('dossier.export_pdf_a11y')}
          >
            {exporting ? (
              <ActivityIndicator size="small" color={theme.accent} />
            ) : (
              <Ionicons name="share-outline" size={16} color={theme.accent} />
            )}
            <Text style={[s.dossierExportText, { color: theme.accent }]}>
              {exporting ? 'Preparing…' : t('dossier.export_report')}
            </Text>
          </Pressable>
        </View>
      )}
    </View>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // Shared section layout (duplicated from parent — matches GradingSection pattern)
  sectionBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  sectionHeaderLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { fontSize: 14, fontWeight: "600" },
  sectionContent: { marginTop: 10 },
  emptyText: {
    fontSize: 13,
    marginTop: 8,
    fontStyle: "italic",
  },
  retryBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 10,
  },
  dossierCard: {
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
  },
  dossierLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  dossierValue: {
    fontSize: 20,
    fontWeight: "700",
  },
  dossierMeta: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 17,
  },
  dossierRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  dossierRowLabel: {
    fontSize: 13,
  },
  dossierRowValue: {
    fontSize: 13,
    fontWeight: "500",
  },
  dossierExportBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 8,
  },
  dossierExportText: {
    fontSize: 13,
    fontWeight: "500",
  },
});
