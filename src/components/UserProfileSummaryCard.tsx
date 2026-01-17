import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  title?: string;
  subtitle?: string;
  totalValueEur: number;
  itemsCount: number;
  dayChangePct?: number | null;
  onRequestChat?: () => void;
};

/**
 * User Profile Summary Card
 * Styled to match the "event card" vibe: clean white square card, bold navy, concise rows.
 */
export default function UserProfileSummaryCard({
  title = "Collector Profile",
  subtitle,
  totalValueEur,
  itemsCount,
  dayChangePct = null,
  onRequestChat,
}: Props) {
  const changeText =
    typeof dayChangePct === "number" && isFinite(dayChangePct)
      ? `${dayChangePct >= 0 ? "+" : ""}${dayChangePct.toFixed(2)}%`
      : "—";

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{title}</Text>
        <View style={styles.pill}>
          <Text style={styles.pillText}>{itemsCount} items</Text>
        </View>
      </View>

      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}

      <View style={styles.valueRow}>
        <Text style={styles.valueLabel}>Total value</Text>
        <Text style={styles.value}>
          €{Number(totalValueEur || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </Text>
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>24h change</Text>
        <Text
          style={[
            styles.metaValue,
            typeof dayChangePct === "number"
              ? dayChangePct >= 0
                ? styles.pos
                : styles.neg
              : null,
          ]}
        >
          {changeText}
        </Text>
      </View>

      <View style={styles.divider} />

      <Pressable
        disabled={!onRequestChat}
        onPress={onRequestChat}
        style={({ pressed }) => [
          styles.chatBtn,
          pressed ? styles.chatBtnPressed : null,
          !onRequestChat ? styles.chatBtnDisabled : null,
        ]}
      >
        <Text style={styles.chatBtnText}>Request to Chat</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d7e6f2",
    borderRadius: 0,
    padding: 14,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  title: {
    color: "#0b1f3a",
    fontSize: 16,
    fontWeight: "900",
  },
  subtitle: {
    marginTop: 6,
    color: "#23405c",
    fontSize: 12,
    fontWeight: "700",
  },
  pill: {
    borderWidth: 1,
    borderColor: "#d7e6f2",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 0,
    backgroundColor: "#f7fbff",
  },
  pillText: {
    color: "#0b1f3a",
    fontSize: 12,
    fontWeight: "900",
  },
  valueRow: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  valueLabel: {
    color: "#23405c",
    fontSize: 12,
    fontWeight: "800",
  },
  value: {
    color: "#0b1f3a",
    fontSize: 20,
    fontWeight: "900",
  },
  metaRow: {
    marginTop: 8,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  metaLabel: {
    color: "#23405c",
    fontSize: 12,
    fontWeight: "800",
  },
  metaValue: {
    color: "#0b1f3a",
    fontSize: 12,
    fontWeight: "900",
  },
  pos: { color: "#0b7a3b" },
  neg: { color: "#b00020" },
  divider: {
    marginTop: 12,
    height: 1,
    backgroundColor: "#d7e6f2",
  },
  chatBtn: {
    marginTop: 12,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#0b1f3a",
    borderRadius: 0,
    paddingVertical: 10,
    alignItems: "center",
  },
  chatBtnPressed: {
    transform: [{ scale: 0.99 }],
  },
  chatBtnDisabled: {
    opacity: 0.5,
  },
  chatBtnText: {
    color: "#0b1f3a",
    fontSize: 13,
    fontWeight: "900",
  },
});
