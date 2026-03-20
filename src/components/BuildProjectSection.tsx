/**
 * Build & Paint project section for item detail screen.
 *
 * Renders a "Build & Paint" header with either a linked project card
 * showing progress bar, or a "Start Build Project" button.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { BETA_MODE } from "@/config/featureFlags";

// ── Props interface ─────────────────────────────────────────────────────

interface BuildProjectSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
  };
  buildAccent: string | undefined;
  linkedProject: { id: string; title: string; pct: number } | null;
  itemIsBuildable: boolean;
  editableName: string;
  itemId: string;
  categorySlug: string;
}

// ── Component ───────────────────────────────────────────────────────────

export const BuildProjectSection = React.memo(function BuildProjectSection({
  theme,
  buildAccent,
  linkedProject,
  editableName,
  itemId,
  categorySlug,
}: BuildProjectSectionProps) {
  const { colors } = useAppTheme();
  if (BETA_MODE) return null;
  return (
    <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
      <View style={s.sectionHeaderRow} accessibilityRole="header">
        <View style={s.sectionHeaderLeft}>
          <Ionicons name="construct-outline" size={20} color={buildAccent ?? theme.accent} />
          <Text style={[s.sectionTitle, { color: theme.text }]}>Build & Paint</Text>
        </View>
      </View>
      {linkedProject ? (
        <Pressable
          onPress={() => router.push(`/projects/${encodeURIComponent(linkedProject.id)}`)}
          style={[s.buildProjectLink, { backgroundColor: theme.background, borderColor: theme.border }]}
          accessibilityRole="button"
          accessibilityLabel={`View build project: ${linkedProject.title}, ${linkedProject.pct}% complete`}
        >
          <View style={[s.buildProjectLinkAccent, { backgroundColor: buildAccent ?? theme.accent }]} />
          <View style={s.buildProjectLinkInfo}>
            <Text style={[s.buildProjectLinkTitle, { color: theme.text }]} numberOfLines={1}>
              {linkedProject.title}
            </Text>
            <View style={s.buildProjectLinkProgressRow}>
              <View style={[s.buildProjectLinkProgressBg, { backgroundColor: theme.border }]}>
                <View
                  style={[
                    s.buildProjectLinkProgressFill,
                    { backgroundColor: buildAccent ?? theme.accent, width: `${linkedProject.pct}%` },
                  ]}
                />
              </View>
              <Text style={[s.buildProjectLinkPct, { color: theme.muted }]}>
                {linkedProject.pct}%
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={theme.muted} />
        </Pressable>
      ) : (
        <Pressable
          onPress={() => router.push({
            pathname: "/build-paint-projects",
            params: { linkItemId: itemId, linkItemName: editableName, linkCategoryId: categorySlug },
          })}
          style={[s.startBuildButton, { backgroundColor: buildAccent ?? theme.accent }]}
          accessibilityRole="button"
          accessibilityLabel="Start a build project for this item"
        >
          <Ionicons name="add-circle-outline" size={18} color={colors.accentText} />
          <Text style={[s.startBuildButtonText, { color: colors.accentText }]}>Start Build Project</Text>
        </Pressable>
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

  buildProjectLink: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    overflow: "hidden",
    marginTop: 8,
  },
  buildProjectLinkAccent: {
    width: 4,
    alignSelf: "stretch",
  },
  buildProjectLinkInfo: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  buildProjectLinkTitle: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 4,
  },
  buildProjectLinkProgressRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  buildProjectLinkProgressBg: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: "hidden",
  },
  buildProjectLinkProgressFill: {
    height: "100%",
    borderRadius: 2,
  },
  buildProjectLinkPct: {
    fontSize: 11,
    fontWeight: "600",
    minWidth: 28,
    textAlign: "right",
  },
  startBuildButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    marginTop: 8,
  },
  startBuildButtonText: {
    // color set inline via colors.accentText
    fontSize: 13,
    fontWeight: "600",
  },
});
