/**
 * SellTimingBadge — shows optimal sell timing for an item.
 *
 * Currently a stub gated behind Premium plan.
 * When the backend `sell_timing_router` is built, this component will
 * call GET /predict/sell-timing/{item_id} and display the recommended
 * sell window (e.g. "Best time to sell: November (+21%)").
 *
 * For now, shows a teaser for Premium users.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { radius, text as textTokens, fontWeight } from "@/theme/tokens";

interface SellTimingBadgeProps {
  itemId: string;
}

function SellTimingBadgeInner({ itemId }: SellTimingBadgeProps) {
  const { colors } = useAppTheme();
  const { plan } = useBillingLimits();

  // Only show for paid plans
  if (plan === "free") return null;

  return (
    <View
      style={[styles.container, { backgroundColor: colors.accent + "0D", borderColor: colors.accent + "30" }]}
      accessibilityRole="text"
      accessibilityLabel="Sell timing coming soon"
    >
      <View style={[styles.iconWrap, { backgroundColor: colors.accent + "20" }]}>
        <Ionicons name="time-outline" size={16} color={colors.accent} />
      </View>
      <View style={styles.textWrap}>
        <Text style={[styles.title, { color: colors.text }]}>Sell Timing</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>Coming soon</Text>
      </View>
      <View style={[styles.badge, { backgroundColor: colors.accent + "15" }]}>
        <Ionicons name="sparkles-outline" size={12} color={colors.accent} />
        <Text style={[styles.badgeText, { color: colors.accent }]}>Premium</Text>
      </View>
    </View>
  );
}

export const SellTimingBadge = React.memo(SellTimingBadgeInner);
SellTimingBadge.displayName = "SellTimingBadge";

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: radius.sm,
    borderWidth: 1,
    marginTop: 10,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.xs,
    alignItems: "center",
    justifyContent: "center",
  },
  textWrap: {
    flex: 1,
    marginLeft: 10,
  },
  title: {
    fontSize: textTokens.md,
    fontWeight: fontWeight.semibold,
  },
  subtitle: {
    fontSize: textTokens.sm,
    marginTop: 1,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  badgeText: {
    fontSize: textTokens.xs,
    fontWeight: fontWeight.semibold,
  },
});
