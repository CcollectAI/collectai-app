/**
 * usePushNotifications
 *
 * Infrastructure hook that:
 *  1. Requests notification permission (triggers the OS dialog)
 *  2. Obtains the Expo push token
 *  3. Registers the token with the backend POST /notifications/register
 *  4. Listens for incoming notifications and notification taps
 *  5. On tap, navigates to the relevant screen via expo-router
 *  6. Manages badge count (increment on receive, clear on app foreground)
 *  7. Sets up Android notification channels
 *
 * Call this hook once at the root layout level after auth has resolved.
 * It is a no-op on web and in environments where expo-notifications is
 * unavailable.
 */

import { useEffect, useRef } from "react";
import { AppState, Linking, Platform, type AppStateStatus } from "react-native";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";
import { collectorsApi } from "@/api/collectorsApi";

// ---------------------------------------------------------------------------
// Configure how notifications appear when the app is in the foreground
// ---------------------------------------------------------------------------
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePushNotifications(userId: string | null) {
  const router = useRouter();
  const notificationListener = useRef<Notifications.EventSubscription | null>(null);
  const responseListener = useRef<Notifications.EventSubscription | null>(null);

  useEffect(() => {
    // Only proceed when we have an authenticated user
    if (!userId) return;

    let cancelled = false;

    async function setup() {
      try {
        // Android notification channels
        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("chat", {
            name: "Chat Messages",
            importance: Notifications.AndroidImportance.HIGH,
            vibrationPattern: [0, 250, 250, 250],
            lightColor: "#81D8D0",
          });
          await Notifications.setNotificationChannelAsync("alerts", {
            name: "Price Alerts",
            importance: Notifications.AndroidImportance.HIGH,
            sound: "default",
          });
          await Notifications.setNotificationChannelAsync("events", {
            name: "Events & Announcements",
            importance: Notifications.AndroidImportance.DEFAULT,
          });
          await Notifications.setNotificationChannelAsync("social", {
            name: "Social",
            importance: Notifications.AndroidImportance.DEFAULT,
          });
          await Notifications.setNotificationChannelAsync("insights", {
            name: "Collection Insights",
            importance: Notifications.AndroidImportance.DEFAULT,
            sound: "default",
          });
        }

        // 1. Request permission
        const { status: existingStatus } =
          await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;

        if (existingStatus !== "granted") {
          const { status } = await Notifications.requestPermissionsAsync();
          finalStatus = status;
        }

        if (finalStatus !== "granted") {
          // User declined — nothing more to do
          return;
        }

        // 2. Get Expo push token
        const tokenData = await Notifications.getExpoPushTokenAsync({
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          projectId: undefined as any, // Uses the project ID from app.json / app.config
        });
        const pushToken = tokenData.data; // e.g. "ExponentPushToken[xxxx]"

        if (cancelled) return;

        // 3. Register with backend
        const platform =
          Platform.OS === "ios"
            ? "ios"
            : Platform.OS === "android"
              ? "android"
              : "unknown";

        await collectorsApi
          .registerPushToken(pushToken, platform)
          .catch(() => {
            // Silently swallow — token registration is best-effort.
            // The app should work fine without push notifications.
          });

        // Clear badge on app open
        try {
          await Notifications.setBadgeCountAsync(0);
        } catch {
          // Silently ignore
        }
      } catch {
        // expo-notifications is not available (web, certain Expo Go versions)
        // or another error occurred — silently ignore.
      }
    }

    setup();

    // 4. Listener: notification received while app is foregrounded
    notificationListener.current =
      Notifications.addNotificationReceivedListener(async (_notification) => {
        // Update badge count when notification received in foreground
        try {
          const badgeCount = await Notifications.getBadgeCountAsync();
          await Notifications.setBadgeCountAsync(badgeCount + 1);
        } catch {
          // Badge count not supported on all platforms
        }
      });

    // 5. Listener: user tapped on a notification
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data as
          | Record<string, unknown>
          | undefined;

        if (!data) return;

        // Direct-to-marketplace: if the notification includes a listing URL, open it directly
        const directUrl = (typeof data.affiliate_url === "string" && data.affiliate_url)
          || (typeof data.listing_url === "string" && data.listing_url);
        if (directUrl) {
          // Validate URL scheme before opening to prevent open redirect attacks
          const ALLOWED_SCHEMES = ["http:", "https:"];
          try {
            const parsed = new URL(directUrl);
            if (ALLOWED_SCHEMES.includes(parsed.protocol)) {
              Linking.openURL(directUrl).catch(() => {});
            }
          } catch {
            // Invalid URL — ignore silently
          }
          return;
        }

        // Value change / weekly digest -> open portfolio
        if (data.type === "value_change" || data.type === "weekly_digest") {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/home/portfolio` as any);
          return;
        }

        // Individual item value change -> open the item
        if (data.type === "item_value_change" && typeof data.item_id === "string" && data.item_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/item/${data.item_id}` as any);
          return;
        }

        if (typeof data.deal_id === "string" && data.deal_id) {
          // Deal notification -> open deal detail
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/purchase/deal/${data.deal_id}` as any);
        } else if (typeof data.item_id === "string" && data.item_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/item/${data.item_id}` as any);
        } else if (typeof data.event_id === "string" && data.event_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/events/${data.event_id}` as any);
        } else if (typeof data.thread_id === "string" && data.thread_id) {
          // Chat message notification -> open the chat thread
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/chat/${data.thread_id}` as any);
        } else if (typeof data.alert_id === "string" && data.alert_id) {
          // Alert notification -> open the alerts tab
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/(tabs)/alerts` as any);
        } else if (typeof data.connection_request_id === "string") {
          // Connection request -> open inbox
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/inbox` as any);
        } else if (typeof data.announcement_id === "string" && data.event_id === undefined) {
          // Event announcement without specific event -> open inbox
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/inbox` as any);
        } else if (typeof data.project_id === "string" && data.project_id) {
          // Build & Paint project notification
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/projects/${data.project_id}` as any);
        } else if (typeof data.category_id === "string" && data.category_id) {
          // Category notification (e.g., price alert for category)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/categories/${data.category_id}` as any);
        } else if (typeof data.user_id === "string" && data.user_id) {
          // User-related notification (e.g., someone followed you)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/users/${data.user_id}` as any);
        }
      });

    // 6. Clear badge when app comes to foreground
    const appStateSubscription = AppState.addEventListener(
      "change",
      async (state: AppStateStatus) => {
        if (state === "active") {
          try {
            await Notifications.setBadgeCountAsync(0);
          } catch {
            // Silently ignore
          }
        }
      },
    );

    return () => {
      cancelled = true;
      if (notificationListener.current) {
        notificationListener.current.remove();
      }
      if (responseListener.current) {
        responseListener.current.remove();
      }
      appStateSubscription.remove();
    };
  }, [userId, router]);
}

export default usePushNotifications;
