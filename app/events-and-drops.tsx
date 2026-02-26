import React, { useEffect, useMemo, useState } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Link, useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
type LoadState = "idle" | "loading" | "loaded" | "error";

type CollectorEventType = "Drop" | "Tournament" | "Stream" | "Showcase";

type CollectorEvent = {
  id: string;
  title: string;
  type: CollectorEventType;
  category: string;
  dateLabel: string;
  timeLabel?: string;
  locationLabel?: string;
  sourceLabel?: string;
};

type TwitchCreator = {
  id: string;
  twitch_login: string;
  display_name: string;
  avatar_url: string | null;
  category: string | null;
  is_partner: boolean;
  is_live: boolean;
  current_title: string | null;
  current_viewers: number | null;
};

const MOCK_EVENTS: CollectorEvent[] = [
  {
    id: "e1",
    title: "Modern Horizons 3 box break",
    type: "Stream",
    category: "Magic: The Gathering",
    dateLabel: "Tonight",
    timeLabel: "20:00 CET",
    locationLabel: "Twitch · CollectAI channel",
    sourceLabel: "Internal / Featured",
  },
  {
    id: "e2",
    title: "Gunpla backlog build night",
    type: "Showcase",
    category: "Gunpla & model kits",
    dateLabel: "Sat · Dec 7",
    timeLabel: "19:30 CET",
    locationLabel: "Local / Online hybrid",
    sourceLabel: "Community",
  },
  {
    id: "e3",
    title: "Disney Lorcana enchanted drop (mock)",
    type: "Drop",
    category: "Disney Lorcana",
    dateLabel: "Next week",
    timeLabel: "TBA",
    locationLabel: "Online · Major retailers",
    sourceLabel: "External calendar (future)",
  },
];

const typeIcon = (type: CollectorEventType): keyof typeof Ionicons.glyphMap => {
  switch (type) {
    case "Drop":
      return "sparkles-outline";
    case "Tournament":
      return "trophy-outline";
    case "Stream":
      return "logo-twitch";
    case "Showcase":
      return "color-palette-outline";
    default:
      return "calendar-outline";
  }
};

const EventsAndDropsScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [state, setState] = useState<LoadState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [creators, setCreators] = useState<TwitchCreator[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  // Load Twitch creators (for live now section)
  const loadData = async () => {
    setState("loading");
    setErrorText(null);

    try {
      if (!supabase || typeof supabase.from !== "function") {
        setState("error");
        setErrorText(
          "Supabase client not configured – Twitch section is running in demo mode."
        );
        return;
      }

      const { data, error } = await supabase
        .from("twitch_creators")
        .select(
          "id, twitch_login, display_name, avatar_url, category, is_partner, is_live, current_title, current_viewers"
        )
        .limit(50);

      if (error) {
        setState("error");
        setErrorText(error.message ?? "Supabase error loading Twitch data.");
        return;
      }

      setCreators((data ?? []) as TwitchCreator[]);
      setState("loaded");
    } catch (err: unknown) {
      setState("error");
      setErrorText(
        err?.message || "Unexpected error while loading Twitch creators."
      );
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadData();
    } finally {
      setRefreshing(false);
    }
  };

  const liveNow = useMemo(
    () =>
      creators
        .filter((c) => c.is_live)
        .sort((a, b) => (b.current_viewers ?? 0) - (a.current_viewers ?? 0)),
    [creators]
  );

  const liveCount = liveNow.length;
  const totalCreators = creators.length;

  const summaryUpcoming = MOCK_EVENTS.length;
  const summaryWatchlistDrops = 3; // mock for now

  const bannerLabel =
    state === "loading"
      ? "Loading Twitch collectors from Supabase…"
      : state === "error"
      ? "Twitch section in demo mode"
      : "Twitch collectors synced with Supabase";

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent ?? '#81D8D0'}
          />
        }
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <View style={{ flex: 1 }}>
            <Text style={[styles.headerLabel, { color: colors.muted }]}>
              Calendar
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Events & drops
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              A simple overview for upcoming drops, build nights and Twitch
              streams so you don&apos;t miss high-signal moments.
            </Text>
          </View>
          <View style={[styles.headerIcon, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons
              name="calendar-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Summary strip */}
        <View
          style={[
            styles.summaryCard,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Upcoming events
            </Text>
            <Text style={[styles.summaryValue, { color: colors.text }]}>
              {summaryUpcoming}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Live Twitch
            </Text>
            <Text style={[styles.summaryValue, { color: "#0BA86C" }]}>
              {liveCount}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Watchlist drops
            </Text>
            <Text style={[styles.summaryValue, { color: colors.text }]}>
              {summaryWatchlistDrops}
            </Text>
          </View>
        </View>

        {/* Sync banner for Twitch */}
        <View
          style={[
            styles.banner,
            {
              backgroundColor:
                state === "error"
                  ? "#EF444415"
                  : state === "loading"
                  ? "#F59E0B15"
                  : colors.accent + "15",
              borderColor:
                state === "error"
                  ? "#EF4444"
                  : state === "loading"
                  ? "#F59E0B"
                  : colors.accent,
            },
          ]}
        >
          <View style={styles.bannerIconBox}>
            {state === "loading" ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <Ionicons
                name={
                  state === "error"
                    ? "warning-outline"
                    : "checkmark-circle-outline"
                }
                size={18}
                color={
                  state === "error"
                    ? "#EF4444"
                    : colors.accent
                }
              />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.bannerTitle, { color: colors.text }]}>
              {bannerLabel}
            </Text>
            <Text style={[styles.bannerBody, { color: colors.muted }]}>
              Later, a small worker can call the Twitch API, update Supabase,
              and this screen will just pick it up.
            </Text>
            {errorText ? (
              <Text
                style={[styles.bannerError, { color: "#EF4444" }]}
                numberOfLines={2}
              >
                {errorText}
              </Text>
            ) : (
              <Text
                style={[styles.bannerError, { color: colors.muted }]}
                numberOfLines={1}
              >
                Tracking {totalCreators} Twitch creators (if configured).
              </Text>
            )}
          </View>
        </View>

        {/* Events & drops list */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.sectionHeaderRow}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              Upcoming events & drops
            </Text>
            <Text style={[styles.sectionHint, { color: colors.muted }]}>
              Mock data for now — Supabase wiring later
            </Text>
          </View>

          {MOCK_EVENTS.map((ev, idx) => (
            <View key={ev.id}>
              <View style={styles.eventRow}>
                <View style={[styles.eventIconCircle, { backgroundColor: colors.accent + '15' }]}>
                  <Ionicons
                    name={typeIcon(ev.type)}
                    size={16}
                    color={colors.accent}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text
                    style={[styles.eventTitle, { color: colors.text }]}
                    numberOfLines={1}
                  >
                    {ev.title}
                  </Text>
                  <Text
                    style={[styles.eventMetaTop, { color: colors.muted }]}
                    numberOfLines={1}
                  >
                    {ev.category} · {ev.type}
                  </Text>
                  <Text
                    style={[styles.eventMetaBottom, { color: colors.muted }]}
                    numberOfLines={2}
                  >
                    {ev.dateLabel}
                    {ev.timeLabel ? ` · ${ev.timeLabel}` : ""}
                    {ev.locationLabel ? ` · ${ev.locationLabel}` : ""}
                  </Text>
                  {ev.sourceLabel && (
                    <Text
                      style={[styles.eventSource, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {ev.sourceLabel}
                    </Text>
                  )}
                </View>
              </View>
              {idx < MOCK_EVENTS.length - 1 && (
                <View
                  style={[
                    styles.separator,
                    { backgroundColor: colors.border },
                  ]}
                />
              )}
            </View>
          ))}
        </View>

        {/* Twitch live now block (Collectors) */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: colors.card,
              borderColor: colors.border,
              marginBottom: 24,
            },
          ]}
        >
          <View style={styles.sectionHeaderRow}>
            <View style={styles.sectionHeaderLeft}>
              <View style={styles.liveDot} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Twitch live now (collectors)
              </Text>
            </View>
            <Link href="/twitch-leaderboard" accessibilityRole="link" accessibilityLabel="View full Twitch leaderboard">
              <Text style={[styles.sectionLink, { color: colors.accent }]}>
                View full leaderboard →
              </Text>
            </Link>
          </View>

          {liveNow.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No collectors live right now. Once your worker marks
              twitch_creators.is_live = true, they&apos;ll appear here.
            </Text>
          ) : (
            liveNow.slice(0, 4).map((c) => (
              <View key={c.id}>
                <View style={styles.liveRow}>
                  <View style={[styles.liveAvatarCircle, { backgroundColor: colors.accent + '15' }]}>
                    <Text style={[styles.liveAvatarInitial, { color: colors.text }]}>
                      {c.display_name?.charAt(0).toUpperCase() ?? "C"}
                    </Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text
                      style={[styles.creatorName, { color: colors.text }]}
                      numberOfLines={1}
                    >
                      {c.display_name}
                    </Text>
                    <Text
                      style={[styles.creatorMeta, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {c.category || "Collectors / Mixed"} ·{" "}
                      {c.current_title || "Live now"}
                    </Text>
                  </View>
                  <View style={styles.liveRight}>
                    <View style={styles.viewerPill}>
                      <Ionicons
                        name="eye-outline"
                        size={12}
                        color="#EF4444"
                        style={{ marginRight: 4 }}
                      />
                      <Text style={styles.viewerPillText}>
                        {c.current_viewers ?? 0}
                      </Text>
                    </View>
                    {c.is_partner && (
                      <Text style={styles.partnerTag}>Partner</Text>
                    )}
                  </View>
                </View>
                <View
                  style={[
                    styles.separator,
                    { backgroundColor: colors.border },
                  ]}
                />
              </View>
            ))
          )}
        </View>
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    padding: 4,
    marginRight: 8,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 16,
    gap: 8,
  },
  backBtn: {
    padding: 4,
    marginTop: 2,
  },
  headerLabel: {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    fontWeight: "600",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 2,
  },
  headerSub: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  summaryCard: {
    flexDirection: "row",
    justifyContent: "space-between",
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  summaryItem: {
    flex: 1,
  },
  summaryLabel: {
    fontSize: 12,
  },
  summaryValue: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 2,
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  bannerTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  bannerBody: {
    fontSize: 11,
    marginTop: 2,
  },
  bannerError: {
    fontSize: 11,
    marginTop: 2,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  sectionHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  sectionHint: {
    fontSize: 11,
  },
  sectionLink: {
    fontSize: 12,
    fontWeight: "600",
  },
  eventRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
  },
  eventIconCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  eventMetaTop: {
    fontSize: 11,
    marginTop: 2,
  },
  eventMetaBottom: {
    fontSize: 11,
    marginTop: 2,
  },
  eventSource: {
    fontSize: 10,
    marginTop: 2,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#EF4444",
    marginRight: 6,
  },
  emptyText: {
    fontSize: 12,
  },
  liveRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
  },
  liveAvatarCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  liveAvatarInitial: {
    fontSize: 14,
    fontWeight: "700",
  },
  creatorName: {
    fontSize: 14,
    fontWeight: "600",
  },
  creatorMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  liveRight: {
    alignItems: "flex-end",
    marginLeft: 8,
  },
  viewerPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: "#EF444415",
  },
  viewerPillText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#EF4444",
  },
  partnerTag: {
    marginTop: 4,
    fontSize: 11,
    fontWeight: "600",
    color: "#A855F7",
  },
});

export default function EventsAndDropsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Events & Drops">
      <EventsAndDropsScreen />
    </ScreenErrorBoundary>
  );
}
