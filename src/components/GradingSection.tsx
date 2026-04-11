/**
 * Grading section for eligible collectible categories.
 *
 * Renders collapsible grading panel with verified grade card,
 * population report table, submit-for-grading buttons, and
 * a certification lookup modal.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import {
  View,
  Text,
  Pressable,
  TextInput,
  ActivityIndicator,
  StyleSheet,
  Linking,
  Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { fireHaptic, HapticIntent } from "@/haptics";
import { formatNumber } from "@/lib/format";
import { useTranslation } from "react-i18next";

// ── Exported types ──────────────────────────────────────────────────────

export type GradingLookupResult = {
  cert_number: string;
  service: string;
  service_name: string;
  item_name: string | null;
  grade: string | null;
  grade_numeric: number | null;
  sub_grades: Record<string, number> | null;
  population_at_grade: number | null;
  population_higher: number | null;
  cert_verified: boolean;
  cert_url: string | null;
  label_type: string | null;
  year: string | null;
  error: string | null;
};

export type PopulationEntry = {
  grade: string;
  count: number;
  pct_of_total: number | null;
};

export type PopulationReport = {
  item_name: string;
  category: string;
  service: string;
  total_graded: number;
  population: PopulationEntry[];
  avg_grade: number | null;
  highest_grade: string | null;
};

export type GradingServiceInfo = {
  id: string;
  name: string;
  short_name: string;
  website: string;
  submission_url: string;
  grade_scale: string;
  categories: string[];
  turnaround: string;
  price_range: string;
};

// ── Props interface ─────────────────────────────────────────────────────

interface GradingSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
    success: string;
  };
  hapticsEnabled: boolean;

  // Expansion state
  gradingExpanded: boolean;
  onToggleExpanded: () => void;

  // Lookup result
  gradingLookupResult: GradingLookupResult | null;

  // Population report
  gradingPopulation: PopulationReport | null;
  gradingPopLoading: boolean;

  // Grading services
  gradingServices: GradingServiceInfo[];

  // Modal state
  gradingModalVisible: boolean;
  onSetGradingModalVisible: (visible: boolean) => void;

  // Cert input state
  gradingCertInput: string;
  onSetGradingCertInput: (value: string) => void;

  // Service picker state
  gradingServicePick: "psa" | "cgc" | "bgs" | "beckett";
  onSetGradingServicePick: (svc: "psa" | "cgc" | "bgs" | "beckett") => void;

  // Lookup handler
  gradingLookupLoading: boolean;
  onGradingLookup: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

function GradingSectionInner({
  theme,
  hapticsEnabled,
  gradingExpanded,
  onToggleExpanded,
  gradingLookupResult,
  gradingPopulation,
  gradingPopLoading,
  gradingServices,
  gradingModalVisible,
  onSetGradingModalVisible,
  gradingCertInput,
  onSetGradingCertInput,
  gradingServicePick,
  onSetGradingServicePick,
  gradingLookupLoading,
  onGradingLookup,
}: GradingSectionProps) {
  const { t } = useTranslation();
  return (
    <>
      {/* Grading Section — collapsible panel */}
      <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
        <Pressable
          onPress={() => {
            onToggleExpanded();
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
          }}
          style={s.sectionHeaderRow}
          accessibilityRole="button"
          accessibilityLabel={`Grading information, ${gradingExpanded ? 'expanded' : 'collapsed'}`}
          accessibilityHint="Double tap to toggle grading details"
        >
          <View style={s.sectionHeaderLeft}>
            <Ionicons name="shield-checkmark-outline" size={20} color={theme.accent} />
            <Text style={[s.sectionTitle, { color: theme.text }]}>Grading</Text>
          </View>
          {!!gradingLookupResult?.cert_verified && (
            <View style={[s.gradingBadge, { backgroundColor: theme.success + '20' }]}>
              <Ionicons name="checkmark-circle" size={14} color={theme.success} />
              <Text style={[s.gradingBadgeText, { color: theme.success }]}>
                {gradingLookupResult.service_name} {gradingLookupResult.grade}
              </Text>
            </View>
          )}
          <Ionicons
            name={gradingExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.muted}
          />
        </Pressable>

        {!!gradingExpanded && (
          <View style={s.sectionContent}>
            {/* Verified grade badge (if lookup was performed) */}
            {!!gradingLookupResult?.cert_verified && (
              <Pressable
                style={[s.gradingVerifiedCard, { backgroundColor: theme.card, borderColor: theme.success + '40' }]}
                onPress={() => {
                  if (gradingLookupResult.cert_url) {
                    Linking.openURL(gradingLookupResult.cert_url);
                  }
                }}
                accessibilityRole="link"
                accessibilityLabel={`View ${gradingLookupResult.service_name} certificate`}
                accessibilityHint="Double tap to open certificate in browser"
              >
                <View style={s.gradingVerifiedHeader}>
                  <Ionicons name="shield-checkmark" size={24} color={theme.success} />
                  <View style={{ flex: 1 }}>
                    <Text style={[s.gradingVerifiedGrade, { color: theme.text }]}>
                      {gradingLookupResult.service_name} {gradingLookupResult.grade}
                    </Text>
                    <Text style={[s.gradingVerifiedMeta, { color: theme.muted }]}>
                      Cert #{gradingLookupResult.cert_number}
                      {gradingLookupResult.year ? ` \u00b7 ${gradingLookupResult.year}` : ''}
                      {gradingLookupResult.label_type ? ` \u00b7 ${gradingLookupResult.label_type}` : ''}
                    </Text>
                  </View>
                  <Ionicons name="open-outline" size={16} color={theme.accent} />
                </View>
                {!!gradingLookupResult.item_name && (
                  <Text style={[s.gradingVerifiedItemName, { color: theme.muted }]}>
                    {gradingLookupResult.item_name}
                  </Text>
                )}
                {!!gradingLookupResult.sub_grades && (
                  <View style={s.gradingSubGradesRow}>
                    {Object.entries(gradingLookupResult.sub_grades).map(([key, val]) => (
                      <View key={key} style={[s.gradingSubGradeChip, { backgroundColor: theme.background }]}>
                        <Text style={[s.gradingSubGradeLabel, { color: theme.muted }]}>
                          {key.charAt(0).toUpperCase() + key.slice(1)}
                        </Text>
                        <Text style={[s.gradingSubGradeValue, { color: theme.text }]}>{val}</Text>
                      </View>
                    ))}
                  </View>
                )}
                <View style={s.gradingPopRow}>
                  {gradingLookupResult.population_at_grade != null && (
                    <Text style={[s.gradingPopText, { color: theme.muted }]}>
                      Pop at grade: {formatNumber(gradingLookupResult.population_at_grade)}
                    </Text>
                  )}
                  {gradingLookupResult.population_higher != null && gradingLookupResult.population_higher > 0 && (
                    <Text style={[s.gradingPopText, { color: theme.muted }]}>
                      {' \u00b7 '}Higher: {formatNumber(gradingLookupResult.population_higher)}
                    </Text>
                  )}
                </View>
              </Pressable>
            )}

            {/* Look Up Certificate button */}
            <Pressable
              style={[s.gradingActionBtn, { borderColor: theme.accent, backgroundColor: theme.card }]}
              onPress={() => {
                onSetGradingModalVisible(true);
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              }}
              accessibilityRole="button"
              accessibilityLabel={t('grading.lookup_a11y')}
              accessibilityHint="Double tap to open certificate lookup form"
            >
              <Ionicons name="search-outline" size={16} color={theme.accent} />
              <Text style={[s.gradingActionBtnText, { color: theme.accent }]}>{t('grading.look_up_certificate')}</Text>
            </Pressable>

            {/* Population Report mini-table */}
            {!!gradingPopLoading && (
              <View style={{ paddingVertical: 16, alignItems: 'center' }}>
                <ActivityIndicator size="small" color={theme.accent} />
                <Text style={[{ fontSize: 12, marginTop: 6 }, { color: theme.muted }]}>{t('grading.loading_population')}</Text>
              </View>
            )}
            {!gradingPopLoading && !!gradingPopulation && (
              <View style={[s.gradingPopTable, { borderColor: theme.border }]}>
                <View style={s.gradingPopTableHeader}>
                  <Text style={[s.gradingPopTableTitle, { color: theme.text }]}>{t('grading.population_report')}</Text>
                  <Text style={[s.gradingPopTableSub, { color: theme.muted }]}>
                    {formatNumber(gradingPopulation.total_graded)} total graded
                    {gradingPopulation.avg_grade != null ? ` \u00b7 Avg: ${gradingPopulation.avg_grade.toFixed(1)}` : ''}
                  </Text>
                </View>
                <View style={[s.gradingPopTableHeaderRow, { borderBottomColor: theme.border }]}>
                  <Text style={[s.gradingPopTableHeaderCell, { color: theme.muted, flex: 1 }]}>Grade</Text>
                  <Text style={[s.gradingPopTableHeaderCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>Count</Text>
                  <Text style={[s.gradingPopTableHeaderCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>%</Text>
                </View>
                {gradingPopulation.population
                  .filter((p) => p.count > 0)
                  .slice(-10)
                  .reverse()
                  .map((entry) => (
                    <View key={entry.grade} style={[s.gradingPopTableRow, { borderBottomColor: theme.border }]}>
                      <Text style={[s.gradingPopTableCell, { color: theme.text, flex: 1, fontWeight: '600' }]}>{entry.grade}</Text>
                      <Text style={[s.gradingPopTableCell, { color: theme.text, flex: 1, textAlign: 'right' }]}>{formatNumber(entry.count)}</Text>
                      <Text style={[s.gradingPopTableCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>
                        {entry.pct_of_total != null ? `${entry.pct_of_total.toFixed(1)}%` : '-'}
                      </Text>
                    </View>
                  ))}
              </View>
            )}

            {/* Submit for Grading buttons */}
            {gradingServices.length > 0 && (
              <View style={s.gradingSubmitSection}>
                <Text style={[s.gradingSubmitTitle, { color: theme.text }]}>{t('grading.submit_for_grading')}</Text>
                <View style={s.gradingSubmitRow}>
                  {gradingServices.slice(0, 4).map((svc) => (
                    <Pressable
                      key={svc.id}
                      style={[s.gradingSubmitBtn, { borderColor: theme.border, backgroundColor: theme.card }]}
                      onPress={() => {
                        Linking.openURL(svc.submission_url);
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                      }}
                      accessibilityRole="link"
                      accessibilityLabel={`Submit to ${svc.short_name}`}
                      accessibilityHint="Double tap to open submission page in browser"
                    >
                      <Text style={[s.gradingSubmitBtnName, { color: theme.text }]}>{svc.short_name}</Text>
                      <Text style={[s.gradingSubmitBtnMeta, { color: theme.muted }]}>{svc.price_range}</Text>
                      <Ionicons name="open-outline" size={12} color={theme.muted} />
                    </Pressable>
                  ))}
                </View>
              </View>
            )}
          </View>
        )}
      </View>

      {/* Grading Certificate Lookup Modal */}
      <Modal
        visible={gradingModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => onSetGradingModalVisible(false)}
      >
        <Pressable
          style={s.modalOverlay}
          onPress={() => onSetGradingModalVisible(false)}
          accessibilityRole="button"
          accessibilityLabel={t('grading.close_modal_a11y')}
        >
          <Pressable
            style={[s.modalSheet, { backgroundColor: theme.card }]}
            onPress={() => {}}
          >
            <View style={s.modalHeader}>
              <Text style={[s.modalTitle, { color: theme.text }]}>{t('grading.look_up_certificate')}</Text>
              <Pressable
                onPress={() => onSetGradingModalVisible(false)}
                accessibilityRole="button"
                accessibilityLabel={t('grading.close_lookup_a11y')}
              >
                <Ionicons name="close" size={24} color={theme.muted} />
              </Pressable>
            </View>

            {/* Service picker */}
            <Text style={[s.modalLabel, { color: theme.text }]}>{t('grading.grading_service')}</Text>
            <View style={s.gradingServicePickerRow}>
              {(['psa', 'cgc', 'bgs', 'beckett'] as const).map((svc) => (
                <Pressable
                  key={svc}
                  style={[
                    s.gradingServicePickerChip,
                    {
                      backgroundColor: gradingServicePick === svc ? theme.accent : theme.background,
                      borderColor: gradingServicePick === svc ? theme.accent : theme.border,
                    },
                  ]}
                  onPress={() => onSetGradingServicePick(svc)}
                  accessibilityRole="radio"
                  accessibilityLabel={`${svc.toUpperCase()} grading service`}
                  accessibilityState={{ selected: gradingServicePick === svc }}
                >
                  <Text
                    style={[
                      s.gradingServicePickerText,
                      { color: gradingServicePick === svc ? '#fff' : theme.text },
                    ]}
                  >
                    {svc.toUpperCase()}
                  </Text>
                </Pressable>
              ))}
            </View>

            {/* Cert number input */}
            <Text style={[s.modalLabel, { color: theme.text, marginTop: 16 }]}>{t('grading.cert_number')}</Text>
            <TextInput
              style={[s.modalInput, { borderColor: theme.border, color: theme.text, backgroundColor: theme.background }]}
              value={gradingCertInput}
              onChangeText={onSetGradingCertInput}
              placeholder="e.g. 12345678"
              placeholderTextColor={theme.muted}
              keyboardType="number-pad"
              returnKeyType="search"
              onSubmitEditing={onGradingLookup}
              autoFocus
            />
            <Text style={[s.modalHint, { color: theme.muted }]}>
              Enter the number printed on your grading certificate or slab label.
            </Text>

            <Pressable
              style={[s.modalConfirmBtn, { backgroundColor: theme.accent, opacity: gradingLookupLoading ? 0.6 : 1 }]}
              onPress={onGradingLookup}
              disabled={gradingLookupLoading}
              accessibilityRole="button"
              accessibilityLabel={t('grading.lookup_cert_a11y')}
              accessibilityState={{ busy: gradingLookupLoading }}
            >
              {gradingLookupLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="search" size={18} color="#fff" />
                  <Text style={s.modalConfirmBtnText}>{t('grading.look_up')}</Text>
                </>
              )}
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // Shared section layout (duplicated from parent — matches CategorySpecificSection pattern)
  sectionBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  sectionHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: { fontSize: 14, fontWeight: '600' },
  sectionContent: { marginTop: 10 },

  // Grading badge (shown in header when verified)
  gradingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginRight: 4,
  },
  gradingBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#059669', // Grading badge — intentionally branded green
  },

  // Verified card
  gradingVerifiedCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  gradingVerifiedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  gradingVerifiedGrade: {
    fontSize: 18,
    fontWeight: '700',
  },
  gradingVerifiedMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  gradingVerifiedItemName: {
    fontSize: 12,
    marginTop: 8,
    fontStyle: 'italic',
  },

  // Sub-grades
  gradingSubGradesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 10,
  },
  gradingSubGradeChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    alignItems: 'center',
  },
  gradingSubGradeLabel: {
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  gradingSubGradeValue: {
    fontSize: 14,
    fontWeight: '700',
    marginTop: 1,
  },

  // Population inline row
  gradingPopRow: {
    flexDirection: 'row',
    marginTop: 8,
  },
  gradingPopText: {
    fontSize: 11,
  },

  // Action button
  gradingActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 12,
  },
  gradingActionBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Population table
  gradingPopTable: {
    borderRadius: 10,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 12,
  },
  gradingPopTableHeader: {
    padding: 12,
  },
  gradingPopTableTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  gradingPopTableSub: {
    fontSize: 11,
    marginTop: 2,
  },
  gradingPopTableHeaderRow: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
  },
  gradingPopTableHeaderCell: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  gradingPopTableRow: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  gradingPopTableCell: {
    fontSize: 13,
  },

  // Submit for grading
  gradingSubmitSection: {
    marginTop: 4,
  },
  gradingSubmitTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  gradingSubmitRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  gradingSubmitBtn: {
    flex: 1,
    minWidth: 120,
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    gap: 3,
  },
  gradingSubmitBtnName: {
    fontSize: 13,
    fontWeight: '700',
  },
  gradingSubmitBtnMeta: {
    fontSize: 10,
  },

  // Service picker (in modal)
  gradingServicePickerRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  gradingServicePickerChip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  gradingServicePickerText: {
    fontSize: 13,
    fontWeight: '700',
  },

  // Modal styles (mirrored from parent's forSaleModal* styles)
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  modalLabel: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 6,
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 8,
  },
  modalHint: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4,
    marginBottom: 8,
  },
  modalConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 12,
  },
  modalConfirmBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
});

export const GradingSection = React.memo(GradingSectionInner);
