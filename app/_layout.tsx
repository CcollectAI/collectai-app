import React from "react";
import { View, Pressable } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SettingsProvider } from "@/lib/settings";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { useSession } from "@/hooks/useSession";
import { ErrorBoundary } from "@/components/ErrorBoundary";

/* ---------- Sentry (guarded so builds work before `npm i`) ---------- */
let Sentry: { init: (opts: Record<string, unknown>) => void; wrap: (component: React.ComponentType) => React.ComponentType } | null = null;
try {
  Sentry = require("@sentry/react-native");
} catch (_) {
  // @sentry/react-native not installed – skip silently
}

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN;
if (Sentry && SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    tracesSampleRate: 0.1,
  });
}

function SettingsHeaderButton() {
  const router = useRouter();
  const { colors } = useAppTheme();
  return (
    <Pressable
      onPress={() => router.push('/settings')}
      style={{ padding: 8, marginRight: 4 }}
      accessibilityRole="button"
      accessibilityLabel="Open settings"
    >
      <Ionicons name="settings-outline" size={22} color={colors.text} />
    </Pressable>
  );
}

function HeaderRight() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <InboxHeaderButton />
      <ThemeToggleButton />
      <SettingsHeaderButton />
    </View>
  );
}

function RootStack() {
  const { colors } = useAppTheme();
  const { user } = useSession();

  // Register push notifications once auth has resolved
  usePushNotifications(user?.id ?? null);

  // Shared screen options with icon-only header
  const iconOnlyHeader = {
    headerTitle: '',
    headerBackTitleVisible: false,
    headerRight: () => <HeaderRight />,
  };

  return (
    <Stack
      screenOptions={{
        headerShown: true,
        headerTitle: '',
        headerBackTitleVisible: false,
        headerRight: () => <HeaderRight />,
        headerStyle: { backgroundColor: colors.card },
        headerTintColor: colors.text,
        headerShadowVisible: false,
      }}
    >
      {/* Tabs group hides Stack header - tabs have their own header */}
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />

      {/* Screens with no header (custom header inside) */}
      <Stack.Screen name="inbox" options={{ headerShown: false }} />
      <Stack.Screen name="chat/[threadId]" options={{ headerShown: false }} />
      <Stack.Screen name="chat/new" options={{ headerShown: false }} />
      <Stack.Screen name="users/[userId]" options={{ headerShown: false }} />

      {/* All other screens: icon-only header (no text) */}
      <Stack.Screen name="item/[id]" options={iconOnlyHeader} />
      <Stack.Screen name="settings" options={iconOnlyHeader} />
      <Stack.Screen name="analytics" options={iconOnlyHeader} />
      <Stack.Screen name="twitch" options={iconOnlyHeader} />
      <Stack.Screen name="build-paint-projects" options={iconOnlyHeader} />
      <Stack.Screen name="categories/index" options={iconOnlyHeader} />
      <Stack.Screen name="categories/[categoryId]" options={iconOnlyHeader} />
      <Stack.Screen name="projects/[id]" options={iconOnlyHeader} />
      <Stack.Screen name="barcode-scan" options={iconOnlyHeader} />
      <Stack.Screen name="quickscan" options={iconOnlyHeader} />
      <Stack.Screen name="add-manual" options={iconOnlyHeader} />
      <Stack.Screen name="events/[eventId]" options={iconOnlyHeader} />
    </Stack>
  );
}

function RootLayout() {
  return (
    <ErrorBoundary>
      <SettingsProvider>
        <RootStack />
      </SettingsProvider>
    </ErrorBoundary>
  );
}

export default Sentry?.wrap ? Sentry.wrap(RootLayout) : RootLayout;
