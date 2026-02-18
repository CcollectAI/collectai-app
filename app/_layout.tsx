import React, { useEffect, useState } from "react";
import { View, Pressable, ActivityIndicator } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SplashScreen from "expo-splash-screen";
import { SettingsProvider } from "@/lib/settings";
import { ToastProvider } from "@/components/Toast";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { AuthProvider } from "@/providers/AuthProvider";
import { useAuthContext } from "@/providers/useAuthContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { OfflineBanner } from "@/components/OfflineBanner";

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

// Keep splash screen visible while auth loads
SplashScreen.preventAutoHideAsync().catch(() => {});

const ONBOARDING_KEY = '@collectai/onboarding_complete';

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

function useProtectedRoute() {
  const { user, loading } = useAuthContext();
  const router = useRouter();
  const segments = useSegments();
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);

  // Check onboarding status once auth resolves
  useEffect(() => {
    if (loading) return;
    if (!user) {
      setOnboardingChecked(true);
      return;
    }
    AsyncStorage.getItem(ONBOARDING_KEY)
      .then((val) => setOnboardingComplete(val === 'true'))
      .catch(() => setOnboardingComplete(false))
      .finally(() => setOnboardingChecked(true));
  }, [loading, user]);

  // Hide splash once we know auth + onboarding state
  useEffect(() => {
    if (!loading && onboardingChecked) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [loading, onboardingChecked]);

  // Redirect based on auth state — runs AFTER the Stack is mounted
  useEffect(() => {
    if (loading || !onboardingChecked) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!user && !inAuthGroup) {
      // Not signed in and not on an auth screen — go to login
      router.replace('/(auth)/login');
    } else if (user && !onboardingComplete && segments[1] !== 'onboarding') {
      // Signed in but hasn't completed onboarding
      router.replace('/(auth)/onboarding');
    } else if (user && onboardingComplete && inAuthGroup) {
      // Signed in + onboarded but still on auth screen — go to tabs
      router.replace('/(tabs)');
    }
  }, [loading, onboardingChecked, user, onboardingComplete, segments]);

  return { loading, onboardingChecked };
}

function RootStack() {
  const { colors } = useAppTheme();
  const { user } = useAuthContext();
  const { loading, onboardingChecked } = useProtectedRoute();

  // Register push notifications once auth has resolved
  usePushNotifications(user?.id ?? null);

  // Shared screen options with icon-only header
  const iconOnlyHeader = {
    headerTitle: '',
    headerBackTitleVisible: false,
    headerRight: () => <HeaderRight />,
  };

  // Show loading overlay while auth resolves, but ALWAYS render the Stack
  // so Expo Router can register all routes
  return (
    <View style={{ flex: 1 }}>
      <Stack
        screenOptions={{
          headerShown: true,
          headerTitle: '',
          headerBackButtonDisplayMode: 'minimal',
          headerRight: () => <HeaderRight />,
          headerStyle: { backgroundColor: colors.card },
          headerTintColor: colors.text,
          headerShadowVisible: false,
        }}
      >
        {/* Auth group — no header */}
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />

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
        <Stack.Screen name="watchlist-builder" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/index" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/create-mandate" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/deal/[dealId]" options={iconOnlyHeader} />

        {/* Subscription & Security */}
        <Stack.Screen name="subscription" options={iconOnlyHeader} />
        <Stack.Screen name="mfa-setup" options={iconOnlyHeader} />

        {/* Legal screens — no header (custom header inside) */}
        <Stack.Screen name="legal/privacy-policy" options={{ headerShown: false }} />
        <Stack.Screen name="legal/terms" options={{ headerShown: false }} />
      </Stack>

      {/* Loading overlay — covers content while auth is resolving */}
      {(loading || !onboardingChecked) && (
        <View
          style={{
            ...({ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 } as const),
            backgroundColor: colors.background,
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 100,
          }}
        >
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      )}
    </View>
  );
}

function RootLayout() {
  return (
    <ErrorBoundary>
      <SettingsProvider>
        <AuthProvider>
          <ToastProvider>
            <RootStack />
            <OfflineBanner />
          </ToastProvider>
        </AuthProvider>
      </SettingsProvider>
    </ErrorBoundary>
  );
}

export default Sentry?.wrap ? Sentry.wrap(RootLayout) : RootLayout;
