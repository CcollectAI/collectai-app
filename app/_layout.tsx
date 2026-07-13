import React, { useEffect, useRef, useState } from "react";
import { View, Pressable, ActivityIndicator, Text, TextInput, Animated as RNAnimated } from "react-native";
import { StatusBar } from "expo-status-bar";
import { Stack, useRouter, useSegments, usePathname, type Href } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SplashScreen from "expo-splash-screen";
import {
  useFonts,
  Roboto_400Regular,
  Roboto_500Medium,
  Roboto_700Bold,
  Roboto_900Black,
} from "@expo-google-fonts/roboto";
import { SettingsProvider } from "@/lib/settings";
import { ToastProvider } from "@/components/Toast";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { usePresenceHeartbeat } from "@/hooks/usePresenceHeartbeat";
import { AuthProvider } from "@/providers/AuthProvider";
import { useAuthContext } from "@/providers/useAuthContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { SafeAreaProvider, initialWindowMetrics } from "react-native-safe-area-context";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { enableFreeze } from "react-native-screens";
import { OfflineBanner } from "@/components/OfflineBanner";
import { isRecoveryPending } from "@/auth/recoveryState";
import { DebugOverlay } from "@/components/DebugOverlay";
import { ExternalTabBar } from "@/components/ExternalTabBar";
import { pushDebugLog } from "@/lib/debugLog";

// Flip to true to re-enable the on-screen [TAB] debug log if the tab bar
// regression resurfaces. Off by default for launch.
// See memory/project_tab_bar_bug_saga.md.
const DEBUG_TAB_BAR = false;

// Disable react-native-screens "freeze on blur" globally. Builds #14-29 had
// a bug where the bottom tab bar dropped all touches on first launch and
// only started responding after the user navigated to a non-tab screen.
// That signature matches RNS freezing the tab navigator's initial state.
// 2026-05-25.
enableFreeze(false);
import { SellerAgeGateProvider } from "@/components/sell/SellerAgeGate";
import { initOfflineQueue } from "@/data/OfflineDataProvider";
import { SplashScreen as BrandedSplash } from "@/components/SplashScreen";
import { recordActiveDay } from "@/hooks/useStoreReview";
import { initAnalytics, trackScreen } from "@/analytics/track";
import { featureFlags } from "@/config/featureFlags";
import { FeatureTourProvider } from "@/lib/featureTour";
// Initialize i18n — side-effect import. Must run before any useTranslation() call.
import "@/i18n";

/* ---------- Global font defaults ----------
 * This monkey-patch runs at import time (before fonts are loaded).
 * The RootLayout component returns null until fontsLoaded is true,
 * keeping the splash screen visible, so users never see unstyled text.
 * If rendering Text outside RootLayout before fonts load, it will
 * fall back to the system font gracefully.
 */
const defaultTextStyle = { fontFamily: "Roboto_400Regular" };
try {
  const origTextRender = (Text as any).render;
  if (origTextRender) {
    (Text as any).render = function (props: any, ref: any) {
      const style = props.style
        ? [defaultTextStyle, props.style]
        : defaultTextStyle;
      return origTextRender.call(this, { ...props, style }, ref);
    };
  }
  const origInputRender = (TextInput as any).render;
  if (origInputRender) {
    (TextInput as any).render = function (props: any, ref: any) {
      const style = props.style
        ? [defaultTextStyle, props.style]
        : defaultTextStyle;
      return origInputRender.call(this, { ...props, style }, ref);
    };
  }
} catch {
  // Font monkey-patch failed — system font will be used as fallback
}

/* ---------- OTA Updates (guarded so dev builds work) ---------- */
let Updates: {
  checkForUpdateAsync?: () => Promise<{ isAvailable: boolean }>;
  fetchUpdateAsync?: () => Promise<unknown>;
} | null = null;
try {
  Updates = require("expo-updates");
} catch (_) {
  // expo-updates not installed or in dev — skip
}

/* ---------- Sentry (guarded so builds work before `npm i`) ---------- */
import { scrubSentryEvent, scrubSentryBreadcrumb } from '@/lib/sentryScrub';

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
    // PII scrubbing — strip emails, tokens, auth headers from any captured
    // event before it leaves the device. Privacy nutrition labels declare
    // we don't share PII for tracking; the beforeSend hook enforces it.
    // Whitelist approach: only user.id is kept (set in AuthProvider.tsx
    // via Sentry.setUser({ id })); everything else gets pattern-scrubbed.
    beforeSend: (event: Record<string, any>) => {
      try {
        return scrubSentryEvent(event);
      } catch {
        // If scrubbing itself throws, drop the event — better to lose
        // a crash report than ship raw PII.
        return null;
      }
    },
    beforeBreadcrumb: (breadcrumb: Record<string, any>) => {
      try {
        return scrubSentryBreadcrumb(breadcrumb);
      } catch {
        return null;
      }
    },
    // Block Sentry SDK from auto-attaching user agent / IP. We override
    // user via setUser({id}) explicitly in AuthProvider.
    sendDefaultPii: false,
  });
}

/* ---------- PostHog Analytics (guarded) ---------- */
if (featureFlags.FEATURE_ANALYTICS) {
  initAnalytics(process.env.EXPO_PUBLIC_POSTHOG_KEY);
}

// Keep splash screen visible while auth loads
SplashScreen.preventAutoHideAsync().catch(() => {});

const ONBOARDING_KEY = '@sparrowcollect/onboarding_complete';

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

  const splashFade = useRef(new RNAnimated.Value(1)).current;
  const [splashHidden, setSplashHidden] = useState(false);

  useEffect(() => {
    if (!loading && onboardingChecked) {
      SplashScreen.hideAsync().catch(() => {});
      RNAnimated.timing(splashFade, {
        toValue: 0,
        duration: 350,
        useNativeDriver: true,
      }).start();
      // Fallback unmount — Animated end-callbacks can be dropped under
      // first-login load (auth + onboarding check + tabs mount in the same
      // frame). Without this, the transparent overlay can keep swallowing
      // taps until the user interacts, blocking the tab bar.
      const t = setTimeout(() => setSplashHidden(true), 400);
      return () => clearTimeout(t);
    }
  }, [loading, onboardingChecked]);

  // Hard ceiling — if AuthProvider.getSession() or AsyncStorage.getItem hang
  // for any reason (flaky network, Keychain weirdness, killed in background),
  // the gates above never fire and the overlay sits with pointerEvents:'auto'
  // forever, blocking the entire UI. Force the splash off after 5s no matter
  // what; the app underneath will show its own loading/error state if needed.
  useEffect(() => {
    const t = setTimeout(() => {
      SplashScreen.hideAsync().catch(() => {});
      setSplashHidden(true);
    }, 5000);
    return () => clearTimeout(t);
  }, []);

  // Combined auth + onboarding gate. Re-reads AsyncStorage on every route
  // change so onboarding completion is picked up immediately after the user
  // finishes the flow (without this, the stale `false` value redirects the
  // user right back into onboarding — the infinite-loop bug reported 2026-05-18).
  const segPath = segments.join('/');
  useEffect(() => {
    if (loading) return;

    const inAuthGroup = segments[0] === '(auth)';
    const onOnboardingScreen = (segments as string[])[1] === 'onboarding';
    const onResetScreen = (segments as string[])[1] === 'reset-password';

    if (!user) {
      setOnboardingComplete(false);
      setOnboardingChecked(true);
      if (!inAuthGroup) router.replace('/(auth)/login');
      return;
    }

    // Password-recovery in progress: keep the user on the reset-password screen
    // (the recovery link sets a session, which would otherwise route them
    // straight into the app via the redirects below). Flag cleared by the screen.
    if (isRecoveryPending()) {
      setOnboardingChecked(true);
      if (!onResetScreen) router.replace('/(auth)/reset-password' as Href);
      return;
    }

    AsyncStorage.getItem(ONBOARDING_KEY)
      .then((val) => {
        const complete = val === 'true';
        setOnboardingComplete(complete);
        setOnboardingChecked(true);

        if (!complete && !onOnboardingScreen && !onResetScreen) {
          router.replace('/(auth)/onboarding');
        } else if (complete && inAuthGroup && !onResetScreen) {
          router.replace('/(tabs)');
        }
      })
      .catch(() => setOnboardingChecked(true));
  }, [loading, user, segPath]);

  return { loading, onboardingChecked, splashFade, splashHidden };
}

function RootStack() {
  const { colors, isDark } = useAppTheme();
  const { user } = useAuthContext();
  const { loading, onboardingChecked, splashFade, splashHidden } = useProtectedRoute();

  // Screen tracking for analytics
  const pathname = usePathname();
  useEffect(() => {
    if (pathname) trackScreen(pathname);
  }, [pathname]);

  // Register push notifications once auth has resolved
  usePushNotifications(user?.id ?? null);

  // Heartbeat for online presence tracking
  usePresenceHeartbeat(user?.id ?? null);

  // Shared screen options with icon-only header
  const iconOnlyHeader = {
    headerTitle: '',
    headerBackTitle: '',
    headerBackButtonDisplayMode: 'minimal' as const,
    headerRight: () => <HeaderRight />,
  };

  // Show loading overlay while auth resolves, but ALWAYS render the Stack
  // so Expo Router can register all routes
  return (
    <View style={{ flex: 1 }}>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerShown: true,
          headerTitle: '',
          headerBackTitle: '',
          headerBackButtonDisplayMode: 'minimal',
          headerRight: () => <HeaderRight />,
          headerStyle: { backgroundColor: colors.card },
          headerTintColor: colors.text,
          headerShadowVisible: false,
          animation: 'slide_from_right',
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
        <Stack.Screen name="chat-demo" options={{ headerShown: false }} />
        <Stack.Screen name="catalog-item/[key]" options={{ headerShown: false }} />
        <Stack.Screen name="users/[userId]" options={{ headerShown: false }} />
        <Stack.Screen name="search" options={{ headerShown: false }} />

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
        <Stack.Screen name="events/[eventId]/announcements" options={iconOnlyHeader} />
        <Stack.Screen name="events/compose-announcement" options={iconOnlyHeader} />
        <Stack.Screen name="create-event" options={iconOnlyHeader} />
        <Stack.Screen name="edit-event" options={iconOnlyHeader} />
        <Stack.Screen name="sponsor/register" options={iconOnlyHeader} />
        <Stack.Screen name="sponsor/dashboard" options={iconOnlyHeader} />
        <Stack.Screen name="watchlist-builder" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/index" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/create-mandate" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/deal/[dealId]" options={iconOnlyHeader} />

        {/* Deal Desk / P2P Selling / Marketplace */}
        <Stack.Screen name="sell/dashboard" options={iconOnlyHeader} />
        <Stack.Screen name="sell/offers" options={iconOnlyHeader} />
        <Stack.Screen name="sell/[offerId]" options={iconOnlyHeader} />

        {/* Subscription & Security */}
        <Stack.Screen name="subscription" options={iconOnlyHeader} />
        <Stack.Screen name="mfa-setup" options={iconOnlyHeader} />

        {/* Additional screens */}
        <Stack.Screen name="alerts" options={iconOnlyHeader} />
        <Stack.Screen name="condition-guide" options={iconOnlyHeader} />
        <Stack.Screen name="leaderboard" options={iconOnlyHeader} />
        <Stack.Screen name="sets-to-complete" options={iconOnlyHeader} />
        <Stack.Screen name="twitch-leaderboard" options={iconOnlyHeader} />

        {/* Legal screens — no header (custom header inside) */}
        <Stack.Screen name="legal/privacy-policy" options={{ headerShown: false }} />
        <Stack.Screen name="legal/terms" options={{ headerShown: false }} />
        <Stack.Screen name="legal/user-policy" options={{ headerShown: false }} />
        <Stack.Screen name="legal/data-processing" options={{ headerShown: false }} />
      </Stack>

      {DEBUG_TAB_BAR && <DebugOverlay />}

      {/* External tab bar — rendered as sibling of Stack to bypass the
          dead-tab-bar bug inside the bottom-tabs navigator. Only visible
          on (tabs) routes. See memory/project_tab_bar_bug_saga.md. */}
      <ExternalTabBar />

      {/* Branded splash overlay — covers content while auth is resolving, fades out */}
      {!splashHidden && (
        <RNAnimated.View
          style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            zIndex: 100,
            opacity: splashFade,
            // pointerEvents in style (RN 0.81+) — the legacy prop on
            // Animated.View is deprecated and can be silently ignored,
            // leaving the transparent overlay catching taps.
            pointerEvents: loading || !onboardingChecked ? 'auto' : 'none',
          }}
        >
          <BrandedSplash />
        </RNAnimated.View>
      )}
    </View>
  );
}

function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    Roboto_400Regular,
    Roboto_500Medium,
    Roboto_700Bold,
    Roboto_900Black,
  });

  // Initialise the offline mutation queue once on mount.
  // This loads any persisted mutations and wires up auto-replay on reconnect.
  useEffect(() => {
    initOfflineQueue();
  }, []);

  // Record active day for store review eligibility
  useEffect(() => {
    recordActiveDay().catch(() => {});
  }, []);

  // Check for OTA updates (non-blocking)
  useEffect(() => {
    if (!Updates?.checkForUpdateAsync) return;
    Updates.checkForUpdateAsync()
      .then((result) => {
        if (result.isAvailable && Updates?.fetchUpdateAsync) {
          return Updates.fetchUpdateAsync();
        }
      })
      .catch(() => {
        // Silently ignore update check failures
      });
  }, []);

  // If fonts fail to load, continue with system fonts rather than hang forever
  if (!fontsLoaded && !fontError) {
    return null; // Splash screen stays visible via preventAutoHideAsync
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
    <ErrorBoundary>
      <SafeAreaProvider initialMetrics={initialWindowMetrics}>
        <SettingsProvider>
          <AuthProvider>
            <FeatureTourProvider>
              <ToastProvider>
                <SellerAgeGateProvider>
                  <RootStack />
                  <OfflineBanner />
                </SellerAgeGateProvider>
              </ToastProvider>
            </FeatureTourProvider>
          </AuthProvider>
        </SettingsProvider>
      </SafeAreaProvider>
    </ErrorBoundary>
    </GestureHandlerRootView>
  );
}

export default Sentry?.wrap ? Sentry.wrap(RootLayout) : RootLayout;
