/**
 * Provenance / Ownership History section for item detail screen.
 *
 * Renders a collapsible "Ownership History" header that wraps
 * the existing ProvenanceTimeline component.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { ProvenanceTimeline } from "@/components/ProvenanceTimeline";

// ── Props interface ─────────────────────────────────────────────────────

interface ProvenanceHistorySectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
  };
  hapticsEnabled: boolean;
  provenanceExpanded: boolean;
  provenanceLoading: boolean;
  provenanceEvents: Array<{
    id: string;
    eventType: string;
    timestamp: string;
    note: string | null;
    source: string | null;
    metadata: Record<string, unknown>;
  }>;
  authenticitySignals: string[];
  onToggleExpanded: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

export const ProvenanceHistorySection = React.memo(function ProvenanceHistorySection({
  theme,
  provenanceExpanded,
  provenanceLoading,
  provenanceEvents,
  authenticitySignals,
  onToggleExpanded,
}: ProvenanceHistorySectionProps) {
  return (
    <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
      <Pressable
        onPress={onToggleExpanded}
        style={s.sectionHeaderRow}
        accessibilityRole="button"
        accessibilityLabel="Toggle item history"
      >
        <View style={s.sectionHeaderLeft}>
          <Ionicons name="time-outline" size={20} color={theme.accent} />
          <Text style={[s.sectionTitle, { color: theme.text }]}>Item History</Text>
        </View>
        {provenanceLoading ? (
          <ActivityIndicator size="small" color={theme.accent} />
        ) : (
          <Ionicons
            name={provenanceExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.muted}
          />
        )}
      </Pressable>
      {provenanceExpanded && (
        <View style={s.sectionContent}>
          <ProvenanceTimeline
            events={provenanceEvents}
            authenticitySignals={authenticitySignals}
            loading={provenanceLoading}
          />
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
});
