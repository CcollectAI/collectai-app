/**
 * usePushNotifications
 *
 * Infrastructure hook that:
 *  1. Requests notification permission (triggers the OS dialog)
 *  2. Obtains the Expo push token
 *  3. Registers the token with the backend POST /notifications/register
 *  4. Listens for incoming notifications and notification taps
 *  5. On tap, navigates to the relevant screen via expo-router
 *
 * Call this hook once at the root layout level after auth has resolved.
 * It is a no-op on web and in environments where expo-notifications is
 * unavailable.
 */

import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";
import { collectorsApi } from "@/api/collectorsApi";

// ---------------------------------------------------------------------------
// Configure how notifications appear when the app is in the foreground
// ---------------------------------------------------------------------------
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowInForeground: true,
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
      } catch {
        // expo-notifications is not available (web, certain Expo Go versions)
        // or another error occurred — silently ignore.
      }
    }

    setup();

    // 4. Listener: notification received while app is foregrounded
    notificationListener.current =
      Notifications.addNotificationReceivedListener((_notification) => {
        // No-op — foreground notifications are handled by the notification
        // handler set above (shows alert + plays sound). Consumers can
        // extend this later for badge counting etc.
      });

    // 5. Listener: user tapped on a notification
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data as
          | Record<string, unknown>
          | undefined;

        if (!data) return;

        if (typeof data.item_id === "string" && data.item_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/item/${data.item_id}` as any);
        } else if (typeof data.event_id === "string" && data.event_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          router.push(`/events/${data.event_id}` as any);
        }
        // Future: add more deep-link targets here (e.g. alerts, chat threads)
      });

    return () => {
      cancelled = true;
      if (notificationListener.current) {
        Notifications.removeNotificationSubscription(
          notificationListener.current,
        );
      }
      if (responseListener.current) {
        Notifications.removeNotificationSubscription(responseListener.current);
      }
    };
  }, [userId, router]);
}

export default usePushNotifications;
