/**
 * Progress tracking section for manga, comics, and retro games.
 *
 * Shows reading/play status pills, progress percentage bar with quick-set
 * buttons, and a notes text input.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React, { useMemo } from "react";
import { View, Text, Pressable, TextInput, ActivityIndicator, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fireHaptic, HapticIntent } from "@/haptics";
import { radius, text, fontWeight, gap } from "@/theme/tokens";

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
  hapticsEnabled: boolean;
  onStatusChange: (status: string) => void;
  onPctChange: (pct: number) => void;
  onNotesChange: (notes: string) => void;
}

export const ItemProgressSection = React.memo(function ItemProgressSection({
  categorySlug,
  progressConfig,
  progressStatus,
  progressPct,
  progressNotes,
  progressLoading,
  progressSaving,
  theme,
  hapticsEnabled,
  onStatusChange,
  onPctChange,
  onNotesChange,
}: ItemProgressSectionProps) {
  const { colors } = useAppTheme();
  const STATUS_COLORS: Record<string, string> = useMemo(() => ({
    not_started: colors.muted,
    reading: colors.accent,
    playing: colors.accent,
    completed: colors.success,
    on_hold: colors.warning,
    plan_to_read: colors.info ?? colors.accent,
    plan_to_play: colors.info ?? colors.accent,
    replaying: colors.accent,
    rereading: colors.accent,
    dropped: colors.danger,
  }), [colors]);

  const normalizedPct = useMemo(() => progressPct ?? 0, [progressPct]);

  const progressBarColor = useMemo(
    () => (progressStatus ? STATUS_COLORS[progressStatus] || theme.accent : theme.accent),
    [progressStatus, STATUS_COLORS, theme.accent],
  );

  const progressBarWidth = useMemo(() => `${normalizedPct}%` as `${number}%`, [normalizedPct]);

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
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                    onStatusChange(status);
                  }}
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
            <Text style={[s.progressBarLabel, { color: theme.muted }]}>Progress: {normalizedPct}%</Text>
            <View style={s.progressBarRow}>
              <View
                style={[s.progressBarBg, { backgroundColor: theme.border }]}
                accessibilityRole="progressbar"
                accessibilityLabel={`${progressConfig.label} progress: ${normalizedPct}%`}
                accessibilityValue={{ min: 0, max: 100, now: normalizedPct }}
              >
                <View
                  style={[
                    s.progressBarFill,
                    {
                      backgroundColor: progressBarColor,
                      width: progressBarWidth,
                    },
                  ]}
                />
              </View>
            </View>
            <View style={s.progressPctButtons}>
              {[0, 25, 50, 75, 100].map((pct) => (
                <Pressable
                  key={pct}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                    onPctChange(pct);
                  }}
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
});

const s = StyleSheet.create({
  sectionBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingBottom: 4,
  },
  sectionHeaderLeft: { flexDirection: "row", alignItems: "center", gap: gap.md },
  sectionTitle: { fontSize: text.lg, fontWeight: fontWeight.bold },
  progressStatusRow: { flexDirection: "row", flexWrap: "wrap", gap: gap.md, paddingTop: 8, paddingBottom: 12 },
  progressStatusPill: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: radius.pill, borderWidth: 1 },
  progressStatusPillText: { fontSize: text.md, fontWeight: fontWeight.semibold },
  progressBarSection: { paddingBottom: 10 },
  progressBarLabel: { fontSize: text.sm, fontWeight: fontWeight.medium, marginBottom: 6 },
  progressBarRow: { flexDirection: "row", alignItems: "center", gap: gap.md },
  progressBarBg: { flex: 1, height: 8, borderRadius: radius.xs, overflow: "hidden" },
  progressBarFill: { height: "100%", borderRadius: radius.xs },
  progressPctButtons: { flexDirection: "row", gap: gap.sm, marginTop: 8 },
  progressPctBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.md, borderWidth: 1 },
  progressPctBtnText: { fontSize: text.xs, fontWeight: fontWeight.semibold },
  progressNotesInput: { borderWidth: 1, borderRadius: radius.sm, padding: 10, minHeight: 60, fontSize: text.md, lineHeight: 18, marginTop: 4 },
});
