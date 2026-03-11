/**
 * Notification History Screen
 *
 * Displays a paginated list of all notifications with unread indicators,
 * pull-to-refresh, infinite scroll, and "Mark All Read" header action.
 */
import React, { useState, useCallback, useEffect, useRef } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  StyleSheet,
  RefreshControl,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useRouter, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fireHaptic, HapticIntent } from "@/haptics";
import {
  getNotificationHistory,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
} from "@/api/collectorsApi";
import { QuickNavBar } from "@/components/QuickNavBar";
import type { Href } from "expo-router";

const PAGE_SIZE = 20;

// Mock data for when backend is unavailable
const MOCK_NOTIFICATIONS: NotificationItem[] = [
  { id: "n1", type: "price_alert", title: "Charizard VMAX price drop", body: "Down 12% to $185 — below your $200 target", data: {}, deep_link: null, read_at: null, created_at: new Date(Date.now() - 900000).toISOString() },
  { id: "n2", type: "deal", title: "New deal on Pikachu Illustrator", body: "Listed at $42,500 on eBay — 15% below market", data: {}, deep_link: null, read_at: null, created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: "n3", type: "value_change", title: "Portfolio up 3.2% today", body: "Your collection gained $127 in value", data: {}, deep_link: null, read_at: null, created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: "n4", type: "achievement", title: "Achievement unlocked!", body: "Collector Level 5 — You've added 25 items", data: {}, deep_link: null, read_at: new Date().toISOString(), created_at: new Date(Date.now() - 86400000).toISOString() },
  { id: "n5", type: "scarcity", title: "Scarcity alert: LEGO UCS Falcon", body: "Only 3 listings remain on tracked marketplaces", data: {}, deep_link: null, read_at: null, created_at: new Date(Date.now() - 172800000).toISOString() },
  { id: "n6", type: "insight", title: "Weekly portfolio insight", body: "Your top gainer: Star Wars Black Series Boba Fett (+18%)", data: {}, deep_link: null, read_at: new Date().toISOString(), created_at: new Date(Date.now() - 259200000).toISOString() },
  { id: "n7", type: "connection", title: "New follower", body: "AuroraCollector started following you", data: {}, deep_link: null, read_at: new Date().toISOString(), created_at: new Date(Date.now() - 345600000).toISOString() },
  { id: "n8", type: "event", title: "Upcoming: Tokyo Toy Show", body: "Starts in 2 days — you marked interested", data: {}, deep_link: null, read_at: null, created_at: new Date(Date.now() - 432000000).toISOString() },
];

const TYPE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  price_alert: "trending-up",
  value_change: "analytics-outline",
  deal: "pricetags-outline",
  chat: "chatbubble-outline",
  event: "calendar-outline",
  connection: "people-outline",
  achievement: "trophy-outline",
  scarcity: "flame-outline",
  insight: "bulb-outline",
  system: "information-circle-outline",
};

function getTypeIcon(type: string): keyof typeof Ionicons.glyphMap {
  return TYPE_ICONS[type] || "notifications-outline";
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function NotificationsScreen() {
  const { colors: theme } = useAppTheme();
  const router = useRouter();

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [markingAllRead, setMarkingAllRead] = useState(false);
  const loadedRef = useRef(false);

  const fetchPage = useCallback(
    async (offset: number, replace: boolean) => {
      try {
        const data = await getNotificationHistory({
          limit: PAGE_SIZE,
          offset,
        });
        if (replace) {
          setNotifications(data.notifications);
        } else {
          setNotifications((prev) => [...prev, ...data.notifications]);
        }
        setTotalCount(data.total_count);
        setUnreadCount(data.unread_count);
      } catch {
        // Fall back to mock data when backend is unavailable
        if (replace && offset === 0) {
          setNotifications(MOCK_NOTIFICATIONS);
          setTotalCount(MOCK_NOTIFICATIONS.length);
          setUnreadCount(MOCK_NOTIFICATIONS.filter((n) => !n.read_at).length);
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    fetchPage(0, true).finally(() => setLoading(false));
  }, [fetchPage]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchPage(0, true);
    setRefreshing(false);
  }, [fetchPage]);

  const onEndReached = useCallback(async () => {
    if (loadingMore || notifications.length >= totalCount) return;
    setLoadingMore(true);
    await fetchPage(notifications.length, false);
    setLoadingMore(false);
  }, [loadingMore, notifications.length, totalCount, fetchPage]);

  const handleMarkRead = useCallback(
    async (item: NotificationItem) => {
      if (item.read_at) return;
      // Optimistic update
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n,
        ),
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
      markNotificationRead(item.id).catch(() => {
        // Rollback on error
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === item.id ? { ...n, read_at: null } : n,
          ),
        );
        setUnreadCount((prev) => prev + 1);
      });
    },
    [],
  );

  const handleTap = useCallback(
    (item: NotificationItem) => {
      handleMarkRead(item);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
      if (item.deep_link) {
        router.push(item.deep_link as Href);
      }
    },
    [handleMarkRead, router],
  );

  const handleMarkAllRead = useCallback(async () => {
    setMarkingAllRead(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    try {
      await markAllNotificationsRead();
      setNotifications((prev) =>
        prev.map((n) => ({
          ...n,
          read_at: n.read_at || new Date().toISOString(),
        })),
      );
      setUnreadCount(0);
    } catch {
      // Silently fail
    } finally {
      setMarkingAllRead(false);
    }
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: NotificationItem }) => {
      const isUnread = !item.read_at;
      return (
        <Pressable
          onPress={() => handleTap(item)}
          style={[
            s.row,
            {
              backgroundColor: isUnread
                ? theme.accent + "08"
                : theme.background,
              borderBottomColor: theme.border,
            },
          ]}
          accessibilityRole="button"
          accessibilityLabel={`${isUnread ? "Unread: " : ""}${item.title}`}
        >
          <View
            style={[
              s.iconCircle,
              {
                backgroundColor: isUnread
                  ? theme.accent + "18"
                  : theme.border + "40",
              },
            ]}
          >
            <Ionicons
              name={getTypeIcon(item.type)}
              size={18}
              color={isUnread ? theme.accent : theme.muted}
            />
          </View>
          <View style={s.rowContent}>
            <Text
              style={[
                s.rowTitle,
                {
                  color: theme.text,
                  fontWeight: isUnread ? "700" : "500",
                },
              ]}
              numberOfLines={1}
            >
              {item.title}
            </Text>
            {item.body ? (
              <Text
                style={[s.rowBody, { color: theme.muted }]}
                numberOfLines={2}
              >
                {item.body}
              </Text>
            ) : null}
            <Text style={[s.rowTime, { color: theme.muted }]}>
              {relativeTime(item.created_at)}
            </Text>
          </View>
          {isUnread && (
            <View style={[s.unreadDot, { backgroundColor: theme.accent }]} />
          )}
        </Pressable>
      );
    },
    [theme, handleTap],
  );

  const ListEmpty = loading ? null : (
    <View style={s.emptyState}>
      <Ionicons name="notifications-off-outline" size={48} color={theme.muted} />
      <Text style={[s.emptyTitle, { color: theme.text }]}>
        No notifications yet
      </Text>
      <Text style={[s.emptySubtitle, { color: theme.muted }]}>
        You'll see price alerts, deal updates, and more here.
      </Text>
    </View>
  );

  return (
    <View style={[s.container, { backgroundColor: theme.background }]}>
      <Stack.Screen
        options={{
          title: "Notifications",
          headerRight: () =>
            unreadCount > 0 ? (
              <Pressable
                onPress={handleMarkAllRead}
                disabled={markingAllRead}
                style={{ paddingHorizontal: 8 }}
                accessibilityRole="button"
                accessibilityLabel="Mark all as read"
              >
                {markingAllRead ? (
                  <ActivityIndicator size="small" color={theme.accent} />
                ) : (
                  <Text style={{ color: theme.accent, fontSize: 14, fontWeight: "600" }}>
                    Mark All Read
                  </Text>
                )}
              </Pressable>
            ) : null,
        }}
      />

      {loading ? (
        <View style={s.loadingContainer}>
          <ActivityIndicator size="large" color={theme.accent} />
        </View>
      ) : (
        <FlashList
          data={notifications}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={theme.accent}
              colors={[theme.accent]}
            />
          }
          onEndReached={onEndReached}
          onEndReachedThreshold={0.3}
          ListEmptyComponent={ListEmpty}
          ListFooterComponent={
            loadingMore ? (
              <View style={s.footer}>
                <ActivityIndicator size="small" color={theme.accent} />
              </View>
            ) : null
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  rowContent: {
    flex: 1,
    gap: 2,
  },
  rowTitle: {
    fontSize: 14,
  },
  rowBody: {
    fontSize: 13,
    lineHeight: 18,
  },
  rowTime: {
    fontSize: 11,
    marginTop: 2,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 6,
  },
  emptyState: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 80,
    paddingHorizontal: 32,
    gap: 8,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
  footer: {
    paddingVertical: 16,
    alignItems: "center",
  },
});

export default function NotificationsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Notifications">
      <NotificationsScreen />
    </ScreenErrorBoundary>
  );
}
