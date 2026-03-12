/**
 * Progress tracking section for manga, comics, and retro games.
 *
 * Shows reading/play status pills, progress percentage bar with quick-set
 * buttons, and a notes text input.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { View, Text, Pressable, TextInput, ActivityIndicator, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";

const STATUS_COLORS_BASE: Record<string, string> = {
  not_started: "#94A3B8",
  reading: "#3B82F6",
  playing: "#3B82F6",
  completed: "#22C55E",
  on_hold: "#F59E0B",
  plan_to_read: "#8B5CF6",
  plan_to_play: "#8B5CF6",
  replaying: "#06B6D4",
  rereading: "#06B6D4",
};

const STATUS_DISPLAY: Record<string, string> = {
  not_started: "Not Started",
  reading: "Reading",
  playing: "Playing",
  completed: "Completed",
  on_hold: "On Hold",
  dropped: "Dropped",
  plan_to_read: "Plan to Read",
  plan_to_play: "Plan to Play",
  replaying: "Replaying",
  rereading: "Re-reading",
};

interface ProgressConfig {
  statuses: string[];
  label: string;
  icon: string;
}

interface ItemProgressSectionProps {
  categorySlug: string;
  progressConfig: ProgressConfig;
  progressStatus: string | null;
  progressPct: number | null;
  progressNotes: string;
  progressLoading: boolean;
  progressSaving: boolean;
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
  };
  onStatusChange: (status: string) => void;
  onPctChange: (pct: number) => void;
  onNotesChange: (notes: string) => void;
}

export function ItemProgressSection({
  categorySlug,
  progressConfig,
  progressStatus,
  progressPct,
  progressNotes,
  progressLoading,
  progressSaving,
  theme,
  onStatusChange,
  onPctChange,
  onNotesChange,
}: ItemProgressSectionProps) {
  const { colors } = useAppTheme();
  const STATUS_COLORS: Record<string, string> = { ...STATUS_COLORS_BASE, dropped: colors.danger };
  return (
    <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
      <View style={s.sectionHeaderRow}>
        <View style={s.sectionHeaderLeft}>
          <Ionicons
            name={(progressConfig.icon as keyof typeof Ionicons.glyphMap) || "book-outline"}
            size={20}
            color={theme.accent}
          />
          <Text style={[s.sectionTitle, { color: theme.text }]}>{progressConfig.label}</Text>
        </View>
        {progressSaving && <ActivityIndicator size="small" color={theme.accent} />}
      </View>

      {progressLoading ? (
        <ActivityIndicator size="small" color={theme.accent} style={{ marginVertical: 12 }} />
      ) : (
        <>
          {/* Status pills */}
          <View style={s.progressStatusRow}>
            {progressConfig.statuses.map((status) => {
              const isActive = progressStatus === status;
              const statusColor = STATUS_COLORS[status] || theme.accent;
              return (
                <Pressable
                  key={status}
                  onPress={() => onStatusChange(status)}
                  style={[
                    s.progressStatusPill,
                    {
                      backgroundColor: isActive ? statusColor : statusColor + "15",
                      borderColor: statusColor,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel={`Set status to ${STATUS_DISPLAY[status]}`}
                  accessibilityState={{ selected: isActive }}
                >
                  <Text style={[s.progressStatusPillText, { color: isActive ? "#fff" : statusColor }]}>
                    {STATUS_DISPLAY[status]}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* Progress bar (percentage) */}
          <View style={s.progressBarSection}>
            <Text style={[s.progressBarLabel, { color: theme.muted }]}>Progress: {progressPct ?? 0}%</Text>
            <View style={s.progressBarRow}>
              <View style={[s.progressBarBg, { backgroundColor: theme.border }]}>
                <View
                  style={[
                    s.progressBarFill,
                    {
                      backgroundColor: progressStatus ? STATUS_COLORS[progressStatus] || theme.accent : theme.accent,
                      width: `${progressPct ?? 0}%`,
                    },
                  ]}
                />
              </View>
            </View>
            <View style={s.progressPctButtons}>
              {[0, 25, 50, 75, 100].map((pct) => (
                <Pressable
                  key={pct}
                  onPress={() => onPctChange(pct)}
                  style={[
                    s.progressPctBtn,
                    {
                      backgroundColor: progressPct === pct ? theme.accent : theme.background,
                      borderColor: theme.border,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel={`Set progress to ${pct}%`}
                >
                  <Text style={[s.progressPctBtnText, { color: progressPct === pct ? "#fff" : theme.muted }]}>
                    {pct}%
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          {/* Progress notes */}
          <TextInput
            style={[s.progressNotesInput, { color: theme.text, borderColor: theme.border, backgroundColor: theme.background }]}
            placeholder={
              categorySlug === "manga" || categorySlug === "comic_books"
                ? 'Reading notes (e.g., "Volume 14 of 37, love the arc!")'
                : 'Play notes (e.g., "Cleared World 5, need to replay boss")'
            }
            placeholderTextColor={theme.muted ?? "#64748B"}
            multiline
            value={progressNotes}
            onChangeText={onNotesChange}
            textAlignVertical="top"
            blurOnSubmit={false}
            accessibilityLabel={`${progressConfig.label} notes`}
          />
        </>
      )}
    </View>
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
  progressStatusRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingTop: 8, paddingBottom: 12 },
  progressStatusPill: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, borderWidth: 1 },
  progressStatusPillText: { fontSize: 13, fontWeight: "600" },
  progressBarSection: { paddingBottom: 10 },
  progressBarLabel: { fontSize: 12, fontWeight: "500", marginBottom: 6 },
  progressBarRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  progressBarBg: { flex: 1, height: 8, borderRadius: 4, overflow: "hidden" },
  progressBarFill: { height: "100%", borderRadius: 4 },
  progressPctButtons: { flexDirection: "row", gap: 6, marginTop: 8 },
  progressPctBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, borderWidth: 1 },
  progressPctBtnText: { fontSize: 11, fontWeight: "600" },
  progressNotesInput: { borderWidth: 1, borderRadius: 10, padding: 10, minHeight: 60, fontSize: 13, lineHeight: 18, marginTop: 4 },
});
