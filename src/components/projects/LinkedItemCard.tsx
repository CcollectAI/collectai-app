/**
 * LinkedItemCard — Shows the item linked to this build/paint project.
 */

import React from "react";
import {
  View,
  Text,
  Image,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import type { BuildPaintProject } from "@/data";

export interface LinkedItemCardProps {
  project: BuildPaintProject;
  categoryName: string | undefined | null;
  accentColor: string;
}

export const LinkedItemCard = React.memo(function LinkedItemCard({
  project,
  categoryName,
  accentColor,
}: LinkedItemCardProps) {
  const { colors } = useAppTheme();

  if (!project.itemId || (!project.itemName && !project.itemImageUrl)) {
    return null;
  }

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Text style={[styles.cardTitle, { color: colors.text }]}>Linked Item</Text>
        <Ionicons name="link-outline" size={16} color={colors.muted} />
      </View>
      <View style={styles.linkedItemRow}>
        {project.itemImageUrl && (
          <Image source={{ uri: project.itemImageUrl }} style={styles.linkedItemImg} />
        )}
        <View style={{ flex: 1 }}>
          <Text style={[styles.linkedItemName, { color: colors.text }]} numberOfLines={2}>
            {project.itemName ?? "Linked item"}
          </Text>
          {categoryName && (
            <View style={styles.linkedItemMeta}>
              {accentColor && <View style={[styles.catDotSm, { backgroundColor: accentColor }]} />}
              <Text style={[styles.linkedItemCat, { color: colors.muted }]}>{categoryName}</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  linkedItemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  linkedItemImg: {
    width: 56,
    height: 56,
    borderRadius: 10,
  },
  linkedItemName: {
    fontSize: 15,
    fontWeight: "600",
  },
  linkedItemMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  catDotSm: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  linkedItemCat: {
    fontSize: 12,
  },
});
