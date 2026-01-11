import React, { useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  Linking,
  StyleSheet,
  Platform,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { EVENTS, CollectorsEvent, EventKind } from "@/data/events";
import { getCategoryById } from "@/data/categories";
import { getUserById } from "@/data/users";
import { typography } from "@/ui/typography";

const BG = "#0b1220";           // deep slate
const CARD = "#0f172a";         // slate card
const CARD_2 = "#0b1426";       // darker card (sections)
const BORDER = "rgba(148,163,184,0.18)";
const TEXT = "#e5e7eb";
const MUTED = "rgba(229,231,235,0.70)";
const MUTED_2 = "rgba(229,231,235,0.55)";
const PRIMARY = "#38D6C7";      // tiffany accent
const NAVY = "#0B1B3A";         // used in light screens; here used sparingly

const kindLabel: Record<EventKind, string> = {
  collection_drop: "Collection drop",
  meetup: "Meetup",
  stream: "Twitch stream",
};

function pillForKind(kind: EventKind) {
  if (kind === "stream") return { bg: "rgba(56,214,199,0.12)", border: "rgba(56,214,199,0.35)", icon: "logo-twitch" as const };
  if (kind === "collection_drop") return { bg: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.35)", icon: "sparkles-outline" as const };
  return { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.35)", icon: "people-outline" as const };
}

const AvatarSmall: React.FC<{ name?: string; color?: string }> = ({ name, color }) => {
  const safeName = (name ?? "").trim();
  const initials =
    safeName.length > 0
      ? safeName
          .split(" ")
          .filter(Boolean)
          .map((part) => part[0])
          .join("")
          .slice(0, 2)
          .toUpperCase()
      : "?";

  return (
    <View style={[styles.avatar, { backgroundColor: color ?? "rgba(14,165,233,0.35)" }]}>
      <Text style={styles.avatarText}>{initials}</Text>
    </View>
  );
};

const Section: React.FC<{ title: string; icon: any; right?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  icon,
  right,
  children,
}) => {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <View style={styles.sectionHeaderLeft}>
          <Ionicons name={icon} size={16} color={MUTED} />
          <Text style={styles.sectionTitle}>{title}</Text>
        </View>
        {right ? <View>{right}</View> : null}
      </View>
      <View style={styles.sectionBody}>{children}</View>
    </View>
  );
};

export default function EventDetailScreen() {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();

  const event: CollectorsEvent | undefined = useMemo(
    () => EVENTS.find((e) => e.id === eventId),
    [eventId]
  );

  const relatedCategory = useMemo(
    () => (event?.categoryId ? getCategoryById(event.categoryId) : undefined),
    [event?.categoryId]
  );

  const hostUser = useMemo(
    () => (event?.hostUserId ? getUserById(event.hostUserId) : undefined),
    [event?.hostUserId]
  );

  const attendeeUsers = useMemo(() => {
    if (!event) return [];
    return event.attendeeIds
      .map((id) => getUserById(id))
      .filter((u): u is NonNullable<ReturnType<typeof getUserById>> => Boolean(u));
  }, [event]);

  // local UI state (later you’ll wire to watchlist/alerts store)
  const [alertsOn, setAlertsOn] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!event) {
    return (
      <View style={styles.notFound}>
        <Text style={styles.notFoundTitle}>Event not found</Text>
        <Text style={styles.notFoundBody}>
          This event doesn’t exist yet. Try opening it again from the Events tab.
        </Text>
        <Pressable onPress={() => router.back()} style={styles.notFoundBtn}>
          <Text style={styles.notFoundBtnText}>Go back</Text>
        </Pressable>
      </View>
    );
  }

  const pill = pillForKind(event.kind);

  const openExternal = async () => {
    if (!event.onlineUrl) return;
    try {
      await Linking.openURL(event.onlineUrl);
    } catch (err) {
      console.log("[EventDetail] failed to open url", err);
    }
  };

  const whenLine = `${event.date}${event.time ? ` • ${event.time}` : ""}`;
  const locationLine = event.location ? String(event.location) : "";

  return (
    <ScrollView
        contentInsetAdjustmentBehavior={Platform.OS === "ios" ? "automatic" : undefined}
      style={{ flex: 1, backgroundColor: BG }}
      contentContainerStyle={styles.container}
    >
      {/* Top nav */}
      <View style={styles.navRow}>
        <Pressable onPress={() => router.back()} style={styles.navBtn} accessibilityRole="button">
          <Ionicons name="chevron-back" size={18} color={TEXT} />
        </Pressable>

        <View style={styles.navCenter}>
          <Text style={styles.kicker}>Events & drops</Text>
          <Text style={styles.navTitle} numberOfLines={1}>Event intel</Text>
        </View>

        <View style={styles.navBtnGhost} />
      </View>

      {/* Hero card */}
      <View style={styles.heroCard}>
        <View style={styles.heroTopRow}>
          <View style={[styles.kindPill, { backgroundColor: pill.bg, borderColor: pill.border }]}>
            <Ionicons name={pill.icon} size={14} color={TEXT} style={{ marginRight: 6, opacity: 0.9 }} />
            <Text style={styles.kindPillText}>{kindLabel[event.kind]}</Text>
          </View>

          <View style={styles.heroActions}>
            <Pressable
              onPress={() => setAlertsOn((v) => !v)}
              style={[styles.iconBtn, alertsOn ? styles.iconBtnOn : null]}
              accessibilityRole="button"
              accessibilityLabel="Toggle alerts"
            >
              <Ionicons
                name={alertsOn ? "notifications" : "notifications-outline"}
                size={18}
                color={alertsOn ? PRIMARY : MUTED}
              />
            </Pressable>

            <Pressable
              onPress={() => setSaved((v) => !v)}
              style={[styles.iconBtn, saved ? styles.iconBtnOn : null]}
              accessibilityRole="button"
              accessibilityLabel="Save event"
            >
              <Ionicons
                name={saved ? "bookmark" : "bookmark-outline"}
                size={18}
                color={saved ? PRIMARY : MUTED}
              />
            </Pressable>
          </View>
        </View>

        <Text style={styles.eventTitle}>{event.title}</Text>

        {event.description ? (
          <Text style={styles.eventDesc} numberOfLines={3}>
            {event.description}
          </Text>
        ) : (
          <Text style={styles.eventDesc} numberOfLines={3}>
            High-signal session for collectors: comps, timing, liquidity, and risk.
          </Text>
        )}

        <View style={styles.heroMetaRow}>
          <View style={styles.metaChip}>
            <Ionicons name="time-outline" size={14} color={MUTED} style={{ marginRight: 6 }} />
            <Text style={styles.metaChipText}>{whenLine}</Text>
          </View>

          {locationLine ? (
            <View style={styles.metaChip}>
              <Ionicons name="location-outline" size={14} color={MUTED} style={{ marginRight: 6 }} />
              <Text style={styles.metaChipText} numberOfLines={1}>{locationLine}</Text>
            </View>
          ) : null}
        </View>

        {event.onlineUrl ? (
          <Pressable onPress={openExternal} style={styles.primaryCta} accessibilityRole="button">
            <Ionicons name="open-outline" size={16} color={NAVY} />
            <Text style={styles.primaryCtaText}>
              {event.kind === "stream" ? "Open stream" : "Open link"}
            </Text>
          </Pressable>
        ) : null}
      </View>

      {/* Professional collector sections */}
      <Section
        title="Overview"
        icon="information-circle-outline"
        right={
          relatedCategory ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{relatedCategory.name}</Text>
            </View>
          ) : null
        }
      >
        <View style={styles.kvRow}>
          <Text style={styles.kvLabel}>Type</Text>
          <Text style={styles.kvValue}>{kindLabel[event.kind]}</Text>
        </View>
        <View style={styles.kvRow}>
          <Text style={styles.kvLabel}>When</Text>
          <Text style={styles.kvValue}>{whenLine}</Text>
        </View>
        <View style={styles.kvRow}>
          <Text style={styles.kvLabel}>Signal</Text>
          <Text style={styles.kvValue}>
            {event.kind === "collection_drop"
              ? "Drop timing + allocation risk"
              : event.kind === "stream"
              ? "Comps + liquidity + sentiment"
              : "Local supply + network edge"}
          </Text>
        </View>
      </Section>

      <Section title="Host & community" icon="people-outline">
        {hostUser ? (
          <View style={styles.personRow}>
            <AvatarSmall name={hostUser.name} color={hostUser.color} />
            <View style={{ flex: 1 }}>
              <Text style={styles.personName}>{hostUser.name}</Text>
              <Text style={styles.personMeta} numberOfLines={1}>
                Host • {event.kind === "stream" ? "Creator" : "Organizer"}
              </Text>
            </View>
            <Pressable
              style={styles.secondaryBtn}
              onPress={() =>
                router.push({
                  pathname: "/chat/new",
                  params: {
                    toUserId: hostUser.id,
                    contextEventId: event.id,
                  },
                })
              }
              accessibilityRole="button"
            >
              <Ionicons name="chatbubble-ellipses-outline" size={16} color={TEXT} />
              <Text style={styles.secondaryBtnText}>Message</Text>
            </Pressable>
          </View>
        ) : (
          <Text style={styles.bodyText}>
            No host is linked yet. Add a hostUserId to the event data to enable DMs.
          </Text>
        )}

        <View style={{ height: 10 }} />

        <Text style={styles.subheading}>Attendees</Text>
        {attendeeUsers.length ? (
          <View style={styles.attendeeWrap}>
            {attendeeUsers.slice(0, 10).map((u) => (
              <View key={u.id} style={styles.attendeeChip}>
                <AvatarSmall name={u.name} color={u.color} />
                <Text style={styles.attendeeName} numberOfLines={1}>{u.name}</Text>
              </View>
            ))}
            {attendeeUsers.length > 10 ? (
              <Text style={[styles.bodyText, { marginTop: 8 }]}>
                +{attendeeUsers.length - 10} more
              </Text>
            ) : null}
          </View>
        ) : (
          <Text style={styles.bodyText}>No attendees yet.</Text>
        )}
      </Section>

      <Section title="Actions" icon="flash-outline">
        <View style={styles.actionsGrid}>
          <Pressable
            style={[styles.actionCard, alertsOn ? styles.actionCardOn : null]}
            onPress={() => setAlertsOn((v) => !v)}
            accessibilityRole="button"
          >
            <Ionicons
              name={alertsOn ? "notifications" : "notifications-outline"}
              size={18}
              color={alertsOn ? PRIMARY : TEXT}
            />
            <Text style={styles.actionTitle}>Drop alerts</Text>
            <Text style={styles.actionBody}>
              {alertsOn ? "You’ll be notified for changes." : "Get notified on time + changes."}
            </Text>
          </Pressable>

          <Pressable
            style={[styles.actionCard, saved ? styles.actionCardOn : null]}
            onPress={() => setSaved((v) => !v)}
            accessibilityRole="button"
          >
            <Ionicons
              name={saved ? "bookmark" : "bookmark-outline"}
              size={18}
              color={saved ? PRIMARY : TEXT}
            />
            <Text style={styles.actionTitle}>Save</Text>
            <Text style={styles.actionBody}>
              {saved ? "Saved to your list." : "Keep this on your radar."}
            </Text>
          </Pressable>
        </View>

        <View style={{ height: 10 }} />

        <Pressable
          style={styles.fullWidthBtn}
          onPress={() => router.push("/watchlist-builder")}
          accessibilityRole="button"
        >
          <Ionicons name="add-circle-outline" size={18} color={PRIMARY} />
          <Text style={styles.fullWidthBtnText}>Add related item to watchlist</Text>
          <Ionicons name="chevron-forward" size={18} color={MUTED_2} />
        </Pressable>
      </Section>

      <View style={{ height: Platform.OS === "ios" ? 26 : 18 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: 16,
    paddingHorizontal: 14,
    paddingBottom: 28,
  },

  navRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  navBtn: {
    width: 40,
    height: 40,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: BORDER,
  },
  navBtnGhost: { width: 40, height: 40, opacity: 0 },
  navCenter: { flex: 1, paddingHorizontal: 10 },
  kicker: { fontSize: 12, fontWeight: "700", color: MUTED, letterSpacing: 0.2 },
  navTitle: { fontSize: 16, fontWeight: "800", color: TEXT, marginTop: 2 },

  heroCard: {
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 18,
    padding: 14,
    marginBottom: 14,
  },
  heroTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  kindPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
  },
  kindPillText: { color: TEXT, fontSize: 12, fontWeight: "800" },

  heroActions: { flexDirection: "row", gap: 10 },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: CARD_2,
    borderWidth: 1,
    borderColor: BORDER,
  },
  iconBtnOn: {
    borderColor: "rgba(56,214,199,0.55)",
    backgroundColor: "rgba(56,214,199,0.10)",
  },

  eventTitle: { fontSize: 20, fontWeight: "900", color: TEXT, lineHeight: 24 },
  eventDesc: {
    marginTop: 8,
    fontSize: 13,
    fontWeight: "650" as any,
    color: MUTED,
    lineHeight: 18,
  },

  heroMetaRow: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 12 },
  metaChip: { ...typography.body, marginTop: 12 },
  metaChipText: { color: TEXT, fontSize: 12, fontWeight: "800" },

  primaryCta: {
    marginTop: 12,
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 14,
    backgroundColor: PRIMARY,
  },
  primaryCtaText: { color: NAVY, fontSize: 13, fontWeight: "900" },

  section: {
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 18,
    padding: 14,
    marginBottom: 14,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  sectionHeaderLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { ...typography.h3 },
  sectionBody: {},

  badge: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    backgroundColor: "rgba(56,214,199,0.10)",
    borderWidth: 1,
    borderColor: "rgba(56,214,199,0.35)",
  },
  badgeText: { color: TEXT, fontSize: 12, fontWeight: "900" },

  kvRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: BORDER,
  },
  kvLabel: { color: MUTED_2, fontSize: 12, fontWeight: "800" },
  kvValue: { color: TEXT, fontSize: 12, fontWeight: "900", flex: 1, textAlign: "right" },

  bodyText: { color: MUTED, fontSize: 13, fontWeight: "650" as any, lineHeight: 18 },
  subheading: { color: TEXT, fontSize: 13, fontWeight: "900", marginBottom: 8 },

  personRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  personName: { ...typography.h3 },
  personMeta: { ...typography.meta, marginTop: 2 },

  secondaryBtn: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 14,
    backgroundColor: CARD_2,
    borderWidth: 1,
    borderColor: BORDER,
  },
  secondaryBtnText: { color: TEXT, fontSize: 12, fontWeight: "900" },

  attendeeWrap: { ...typography.body, marginTop: 12 },
  attendeeChip: { ...typography.body, marginTop: 12 },
  attendeeName: { color: TEXT, fontSize: 12, fontWeight: "900", flex: 1 },

  avatar: {
    width: 30,
    height: 30,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { color: TEXT, fontSize: 11, fontWeight: "900" },

  actionsGrid: { flexDirection: "row", gap: 10 },
  actionCard: {
    flex: 1,
    borderRadius: 16,
    backgroundColor: CARD_2,
    borderWidth: 1,
    borderColor: BORDER,
    padding: 12,
    gap: 8,
  },
  actionCardOn: {
    borderColor: "rgba(56,214,199,0.55)",
    backgroundColor: "rgba(56,214,199,0.08)",
  },
  actionTitle: { color: TEXT, fontSize: 13, fontWeight: "900" },
  actionBody: { color: MUTED, fontSize: 12, fontWeight: "800", lineHeight: 16 },

  fullWidthBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: CARD_2,
    borderWidth: 1,
    borderColor: BORDER,
  },
  fullWidthBtnText: { flex: 1, color: TEXT, fontSize: 12, fontWeight: "900" },

  notFound: {
    flex: 1,
    backgroundColor: BG,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
  },
  notFoundTitle: { fontSize: 16, fontWeight: "800", color: TEXT, marginBottom: 8 },
  notFoundBody: { fontSize: 13, color: MUTED, textAlign: "center", lineHeight: 18 },
  notFoundBtn: {
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    backgroundColor: CARD,
  },
  notFoundBtnText: { fontSize: 13, fontWeight: "900", color: TEXT },
});