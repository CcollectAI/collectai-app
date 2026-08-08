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
import { useRouter, type Href } from "expo-router";
import { collectorsApi } from "@/api/collectorsApi";
import { recordPushImpression, recordPushInteraction } from "@/api/intelligenceApi";
import { trackTap } from "@/lib/notificationOutcomeTracker";
import { itemHref, inAppListingHref } from "@/lib/ids";
import { logger } from '@/lib/logger';

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
          projectId: undefined!, // Uses the project ID from app.json / app.config
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
        } catch (e) {
          logger.error('[silent-catch] usePushNotifications.ts:126:', e);
          // Silently ignore
        }
      } catch (e) {
        logger.error('[silent-catch] usePushNotifications.ts:129:', e);
        // expo-notifications is not available (web, certain Expo Go versions)
        // or another error occurred — silently ignore.
      }
    }

    setup();

    // 4. Listener: notification received while app is foregrounded
    notificationListener.current =
      Notifications.addNotificationReceivedListener(async (notification) => {
        // Push-engagement loop: record impression with the backend so
        // notification_impressions starts collecting. notification_id was
        // injected into the data payload by send_push_to_user (commit
        // 93ea969).
        const data = notification.request.content.data as
          | Record<string, unknown>
          | undefined;
        const notificationId =
          (typeof data?.notification_id === "string" && data.notification_id) || null;
        if (notificationId) {
          recordPushImpression(notificationId, {
            appState: AppState.currentState,
            platform: Platform.OS,
            receivedAt: new Date().toISOString(),
          });
        }

        // Update badge count when notification received in foreground
        try {
          const badgeCount = await Notifications.getBadgeCountAsync();
          await Notifications.setBadgeCountAsync(badgeCount + 1);
        } catch (e) {
          logger.error('[silent-catch] usePushNotifications.ts:161:', e);
          // Badge count not supported on all platforms
        }
      });

    // 5. Listener: user tapped on a notification
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data as
          | Record<string, unknown>
          | undefined;

        // Push-engagement loop: record interaction + arm the outcome
        // tracker so subsequent user actions can be attributed back to
        // this notification (see notificationOutcomeTracker.ts).
        const notificationId =
          (typeof data?.notification_id === "string" && data.notification_id) || null;
        if (notificationId) {
          const isDefault =
            response.actionIdentifier === Notifications.DEFAULT_ACTION_IDENTIFIER;
          const isDismiss =
            response.actionIdentifier === "expo.modules.notifications.actions.DISMISS";
          const kind = isDefault ? "open" : isDismiss ? "dismiss" : "action";
          recordPushInteraction(notificationId, kind, {
            action_id: response.actionIdentifier,
          });
          if (kind === "open" || kind === "action") {
            trackTap(notificationId);
          }
        }

        if (!data) return;

        // Direct-to-marketplace: if the notification includes a listing URL, open it directly
        const directUrl = (typeof data.affiliate_url === "string" && data.affiliate_url)
          || (typeof data.listing_url === "string" && data.listing_url);
        if (directUrl) {
          // Our OWN listings resolve to a screen in this app, so route rather
          // than hand them to the browser — a member Target Hit otherwise left
          // the app for a URL that 404s. Checked first: the scheme validation
          // below would happily open it.
          const internal = inAppListingHref(directUrl);
          if (internal) { router.push(internal); return; }
          // Validate URL scheme before opening to prevent open redirect attacks
          const ALLOWED_SCHEMES = ["http:", "https:"];
          try {
            const parsed = new URL(directUrl);
            if (ALLOWED_SCHEMES.includes(parsed.protocol)) {
              Linking.openURL(directUrl).catch(() => {});
            }
          } catch (e) {
            logger.error('[silent-catch] usePushNotifications.ts:205:', e);
            // Invalid URL — ignore silently
          }
          return;
        }

        // Value change / weekly digest -> open portfolio
        if (data.type === "value_change" || data.type === "weekly_digest") {
          router.push(`/(tabs)/` as Href);
          return;
        }

        // Individual item value change -> open the item.
        // `data.item_id` is whatever the sending worker put there. Most send an
        // items uuid, but the low-value worker sends `price_predictions.item_ref`
        // — a catalog key — so route by identifier shape, not by assumption.
        if (data.type === "item_value_change" && typeof data.item_id === "string" && data.item_id) {
          const href = itemHref(data.item_id);
          if (href) router.push(href);
          return;
        }

        if (typeof data.deal_id === "string" && data.deal_id) {
          router.push(`/purchase/deal/${data.deal_id}` as Href);
        } else if (typeof data.item_id === "string" && data.item_id) {
          const href = itemHref(data.item_id);
          if (href) router.push(href);
        } else if (typeof data.event_id === "string" && data.event_id) {
          router.push(`/events/${data.event_id}` as Href);
        } else if (typeof data.thread_id === "string" && data.thread_id) {
          router.push(`/chat/${data.thread_id}` as Href);
        } else if (typeof data.alert_id === "string" && data.alert_id) {
          // `/(tabs)/alerts` never existed — alerts was never a tab, and the
          // standalone app/alerts.tsx was merged into the notifications screen
          // on 2026-08-08. A push carrying alert_id landed on an Unmatched
          // route: the notification arrives, the user taps it, and the app
          // shows a 404 screen. Caught by `node scripts/check-dead-nav.mjs`,
          // which is exactly what that gate is for.
          router.push(`/notifications` as Href);
        } else if (typeof data.connection_request_id === "string") {
          router.push(`/inbox` as Href);
        } else if (typeof data.announcement_id === "string" && data.event_id === undefined) {
          router.push(`/inbox` as Href);
        } else if (typeof data.project_id === "string" && data.project_id) {
          router.push(`/projects/${data.project_id}` as Href);
        } else if (typeof data.category_id === "string" && data.category_id) {
          router.push(`/categories/${data.category_id}` as Href);
        } else if (typeof data.user_id === "string" && data.user_id) {
          router.push(`/users/${data.user_id}` as Href);
        }
      });

    // 6. Clear badge when app comes to foreground
    const appStateSubscription = AppState.addEventListener(
      "change",
      async (state: AppStateStatus) => {
        if (state === "active") {
          try {
            await Notifications.setBadgeCountAsync(0);
          } catch (e) {
            logger.error('[silent-catch] usePushNotifications.ts:258:', e);
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
