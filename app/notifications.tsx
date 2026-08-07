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
import { SkeletonList } from "@/components/Skeleton";
import { fireHaptic, HapticIntent } from "@/haptics";
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import {
  getNotificationHistory,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
} from "@/api/collectorsApi";
import { QuickNavBar } from "@/components/QuickNavBar";
import logger from '@/utils/logger';
import type { Href } from "expo-router";
import { timeAgo } from "@/lib/timeAgo";
import { openAffiliateUrl } from "@/utils/affiliateHelpers";
import { MS_PER_WEEK } from "@/constants/time";

const PAGE_SIZE = 20;


const TYPE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  price_alert: "trending-up",
  price_drop: "trending-down",
  value_change: "analytics-outline",
  deal: "pricetags-outline",
  deal_alert: "pricetags-outline",
  chat: "chatbubble-outline",
  new_message: "chatbubble-outline",
  event: "calendar-outline",
  event_invite: "calendar-outline",
  connection: "people-outline",
  achievement: "trophy-outline",
  set_complete: "trophy-outline",
  scarcity: "flame-outline",
  insight: "bulb-outline",
  catalog_mapped: "checkmark-done-outline",
  sponsor_message: "megaphone-outline",
  // DSA Art 17 statement of reasons — written by /ops/listing-reports/{id}/action
  // when a reported listing is decided. Distinct from `system` because it is a
  // decision ABOUT the recipient's own content and carries a redress route.
  moderation: "shield-outline",
  system: "information-circle-outline",
};

function getTypeIcon(type: string): keyof typeof Ionicons.glyphMap {
  return TYPE_ICONS[type] || "notifications-outline";
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < MS_PER_WEEK) return timeAgo(iso);
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
      } catch (err) {
        // logger.error, not .warn — warn is stripped from TestFlight builds.
        logger.error('[Notifications] fetch failed:', err);
        // NO mock fallback. This used to substitute 8 fabricated notifications
        // (invented price drops, deals, followers) that a user could not tell
        // from real ones — so a total backend outage rendered as a healthy,
        // populated inbox. An empty list is honest; the empty state renders.
        if (replace && offset === 0) {
          setNotifications([]);
          setTotalCount(0);
          setUnreadCount(0);
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
      markNotificationRead(item.id).catch((err) => {
        logger.info('[Notifications] mark-read rollback:', err);
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
      if (!item.deep_link) return;

      // A deal notification's destination is the marketplace listing, which is
      // an https URL — router.push would treat it as an in-app route and go
      // nowhere. openAffiliateUrl validates the scheme and records the click,
      // so a notification tap counts as routed GMV like any other Shop tap.
      if (/^https?:\/\//i.test(item.deep_link)) {
        // No `category` — openAffiliateUrl forwards it to record_demand_signal,
        // whose `category` column holds a COLLECTIBLE slug (pokemon, lego).
        // `item.type` is a notification type ('deal_alert'), so passing it would
        // quietly poison the demand-signal category dimension.
        openAffiliateUrl(item.deep_link);
        return;
      }
      router.push(item.deep_link as Href);
    },
    [handleMarkRead, router],
  );

  const handleMarkAllRead = useCallback(async () => {
    setMarkingAllRead(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    // Optimistically update UI before API call
    const previousNotifications = notifications;
    const previousUnreadCount = unreadCount;
    setNotifications((prev) =>
      prev.map((n) => ({
        ...n,
        read_at: n.read_at || new Date().toISOString(),
      })),
    );
    setUnreadCount(0);

    try {
      await markAllNotificationsRead();
    } catch (err) {
      logger.error('[Notifications] mark-all-read failed:', err);
      // Rollback on failure
      setNotifications(previousNotifications);
      setUnreadCount(previousUnreadCount);
    } finally {
      setMarkingAllRead(false);
    }
  }, [notifications, unreadCount]);

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
                  fontWeight: isUnread ? fw.bold : fw.medium,
                },
              ]}
              numberOfLines={1}
            >
              {item.title}
            </Text>
            {item.body ? (
              <Text
                style={[s.rowBody, { color: theme.muted }]}
                // A moderation notice is the DSA Art 17 statement of reasons,
                // and it is only a valid statement if the recipient can read
                // it. Truncating at two lines cut it mid-sentence, and the
                // deep link goes to the listing that was removed, not to the
                // text — so the required content was unreadable anywhere in
                // the app. Rare enough that an untruncated row costs nothing.
                numberOfLines={item.type === 'moderation' ? undefined : 2}
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
                  <Text style={{ color: theme.accent, fontSize: textToken.md, fontWeight: fw.semibold }}>
                    Mark All Read
                  </Text>
                )}
              </Pressable>
            ) : null,
        }}
      />

      {loading ? (
        <View style={s.loadingContainer}>
          <SkeletonList count={6} type="row" />
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
    fontSize: textToken.md,
  },
  rowBody: {
    fontSize: textToken.md,
    lineHeight: 18,
  },
  rowTime: {
    fontSize: textToken.xs,
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
    fontSize: textToken.xl,
    fontWeight: fw.bold,
    marginTop: 8,
  },
  emptySubtitle: {
    fontSize: textToken.md,
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
