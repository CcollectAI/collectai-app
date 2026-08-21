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
import { HeaderActions } from '@/components/HeaderActions';
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
} catch (e) {
  logger.error('[silent-catch] _layout.tsx:81:', e);
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
  logger.error('[silent-catch] _layout.tsx:92:', _);
  // expo-updates not installed or in dev — skip
}

/* ---------- Sentry (guarded so builds work before `npm i`) ---------- */
import { scrubSentryEvent, scrubSentryBreadcrumb } from '@/lib/sentryScrub';
import { logger, setLogSink } from '@/lib/logger';
import { fonts } from '@/theme/tokens';
import { safeGoBack } from '@/lib/goBack';

let Sentry: {
  init: (opts: Record<string, unknown>) => void;
  wrap: (component: React.ComponentType) => React.ComponentType;
  captureMessage: (message: string, level?: string) => void;
  addBreadcrumb: (breadcrumb: Record<string, unknown>) => void;
} | null = null;
try {
  Sentry = require("@sentry/react-native");
} catch (_) {
  logger.error('[silent-catch] _layout.tsx:102:', _);
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
      } catch (e) {
        logger.error('[silent-catch] _layout.tsx:119:', e);
        // If scrubbing itself throws, drop the event — better to lose
        // a crash report than ship raw PII.
        return null;
      }
    },
    beforeBreadcrumb: (breadcrumb: Record<string, any>) => {
      try {
        return scrubSentryBreadcrumb(breadcrumb);
      } catch (e) {
        logger.error('[silent-catch] _layout.tsx:128:', e);
        return null;
      }
    },
    // Block Sentry SDK from auto-attaching user agent / IP. We override
    // user via setUser({id}) explicitly in AuthProvider.
    sendDefaultPii: false,
  });

  // Forward retained logs to Sentry.
  //
  // Why this exists: `logger.error` wrote to the console and NOWHERE else, so
  // the one line built to triage the paywall —
  // "[subscription] iapUnavailable reason=no-offering" — could not be read on
  // a TestFlight device without a cable and Console.app. Sentry was
  // initialised the whole time and never received it, and `getRecentLogs()`
  // had no consumer. The diagnostic existed and was unreachable.
  //
  //   error -> a real event. An error nothing captures is exactly the silent
  //            failure this repo keeps rediscovering.
  //   warn  -> a breadcrumb, so the event above arrives with its run-up
  //            attached instead of as one bare line.
  //   debug/info are not forwarded: they are console noise and would burn
  //            quota without telling us anything a breadcrumb does not.
  //
  // Both paths go through `beforeSend` / `beforeBreadcrumb`, so the PII scrub
  // configured above applies to log text exactly as it does to exceptions —
  // this adds a new source of strings, not a new way to leak them.
  setLogSink((entry) => {
    if (entry.level === 'error') {
      Sentry?.captureMessage(entry.message, 'error');
    } else if (entry.level === 'warn') {
      Sentry?.addBreadcrumb({
        category: 'log',
        level: 'warning',
        message: entry.message,
      });
    }
  });
}

/* ---------- PostHog Analytics (guarded) ---------- */
if (featureFlags.FEATURE_ANALYTICS) {
  initAnalytics(process.env.EXPO_PUBLIC_POSTHOG_KEY);
}

// Keep splash screen visible while auth loads
SplashScreen.preventAutoHideAsync().catch(() => {});

const ONBOARDING_KEY = '@sparrowcollect/onboarding_complete';

// Header bar-button frame. MUST stay square: iOS 26 draws its circular "liquid
// glass" capsule sized to the button's frame, so a non-square frame renders as
// an oval with the glyph off its centre. Padding around an icon does NOT give a
// square — a glyph's advance width is narrower than its line height.
const HEADER_BTN = {
  width: 40,
  height: 40,
  alignItems: 'center' as const,
  justifyContent: 'center' as const,
};

// Optical centring for the back chevron ONLY.
//
// Measured (fontTools, Ionicons.ttf, upem 512): `chevron-back` ink spans
// x[160,352] against a 512 advance — geometrically dead-centre, dx = 0.00pt.
// But a "<" is not optically centred when it is geometrically centred: the
// vertex is a single point on the left while both arms terminate on the right,
// so the mass reads right-of-centre inside a circle. Hence the nudge.
//
// It is a TRANSFORM, not margin/padding, on purpose: the iOS 26 capsule is
// drawn from the Pressable's frame, and transforms are layout-neutral, so the
// circle stays put and only the glyph inside it moves. Changing padding here
// would move the capsule too — see docs/ui-playbook.md.
const BACK_CHEVRON_OPTICAL = { transform: [{ translateX: -1.5 }] };


/** Native-header back button that cannot dead-end. See `iconOnlyHeader`. */
function HeaderBackButton({ color }: { color?: string } = {}) {
  const router = useRouter();
  const { colors } = useAppTheme();
  return (
    <Pressable
      onPress={() => safeGoBack(router)}
      // FIXED SQUARE, not padding. iOS 26 sizes its capsule to this frame, and
      // an icon glyph's advance width is narrower than its line height — so
      // `padding: 8` produced a non-square frame (oval capsule) with the chevron
      // sitting off its centre. An explicit square + centred content makes the
      // capsule a true circle and centres the glyph inside it.
      style={HEADER_BTN}
      accessibilityRole="button"
      accessibilityLabel="Go back"
    >
      <Ionicons
        name="chevron-back"
        size={24}
        color={color ?? colors.text}
        style={BACK_CHEVRON_OPTICAL}
      />
    </Pressable>
  );
}

/** `color` overrides the theme tint — needed on the black camera header,
 *  where the default `colors.text` is near-invisible in light mode. */
function HeaderRight({ color }: { color?: string } = {}) {
  return (
    <HeaderActions color={color} />
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

  // Shared screen options with icon-only header.
  //
  // `headerLeft` replaces the NATIVE back button on purpose. The native one
  // calls `goBack()` on the navigator, which is a silent no-op when the stack
  // has nothing to pop — the chevron is drawn, it animates, and nothing
  // happens. Reported on settings and notifications, both of which use this
  // options object. `safeGoBack` falls back to the tabs so the control always
  // does something. The in-body equivalents (ScreenHeader, and every
  // `router.back()` call site) are guarded the same way, and
  // `npm run check:back` keeps them that way.
  const iconOnlyHeader = {
    headerTitle: '',
    headerBackTitle: '',
    headerBackButtonDisplayMode: 'minimal' as const,
    headerLeft: () => <HeaderBackButton />,
    headerRight: () => <HeaderRight />,
  };

  // QuickScan is a full-bleed black camera screen. With the default
  // `colors.card` header it rendered as a white band above the viewfinder in
  // light mode. Header stays SHOWN — AnalyzingScreen, BatchSummaryScreen and
  // MultiItemOverlay have no back affordance of their own, so hiding it would
  // strand the user on those phases.
  const cameraHeader = {
    ...iconOnlyHeader,
    headerStyle: { backgroundColor: '#000000' },
    headerTintColor: '#FFFFFF',
    // headerLeft must be overridden too, not just headerRight. `headerTintColor`
    // only tints the NATIVE back button; the custom one inherited from
    // iconOnlyHeader defaults to `colors.text`, which on this black header is
    // near-invisible in light mode — the same reason headerRight is overridden.
    headerLeft: () => <HeaderBackButton color="#FFFFFF" />,
    headerRight: () => <HeaderRight color="#FFFFFF" />,
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
          // ANDROID ONLY. @react-navigation/native-stack ignores
          // headerTitleAlign on iOS — the native bar always centres its title.
          // Verified the hard way: a long title ("Comic Books & Graphic
          // Novels") fills the bar and LOOKS left-aligned, while a short one
          // ("Help") is obviously still centred. The iOS fix is not this
          // option, it is not setting a native title at all on screens that
          // already show their own heading in the body. 2026-08-16.
          headerTitleAlign: 'left' as const,
          // The native bar draws its title with UIKit, NOT with an RN <Text>,
          // so the `Text.render` monkey-patch at the top of this file — which
          // is what puts Roboto on every other string in the app — never
          // reaches it. With no headerTitleStyle anywhere, 26 screens rendered
          // their title in San Francisco on iOS while the body beneath them was
          // Roboto. Invisible on Android, where the system font IS Roboto,
          // which is exactly why it survived a title sweep that fixed size,
          // weight and alignment. Measured 2026-08-21.
          headerTitleStyle: { fontFamily: fonts.bold },
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
        {/* headerShown:false at registration (not just in-component) so the
            native glass header never flashes during the push transition — the
            screens render their own flat ScreenHeader instead. */}
        <Stack.Screen name="categories/[categoryId]" options={{ headerShown: false }} />
        <Stack.Screen name="category-browse" options={{ headerShown: false }} />
        <Stack.Screen name="projects/[id]" options={iconOnlyHeader} />
        <Stack.Screen name="barcode-scan" options={cameraHeader} />
        <Stack.Screen name="quickscan" options={cameraHeader} />
        <Stack.Screen name="add-manual" options={iconOnlyHeader} />
        <Stack.Screen name="events/[eventId]" options={iconOnlyHeader} />
        <Stack.Screen name="events/[eventId]/announcements" options={iconOnlyHeader} />
        <Stack.Screen name="events/compose-announcement" options={iconOnlyHeader} />
        <Stack.Screen name="create-event" options={iconOnlyHeader} />
        <Stack.Screen name="edit-event" options={iconOnlyHeader} />
        <Stack.Screen name="sponsor/register" options={iconOnlyHeader} />
        <Stack.Screen name="sponsor/dashboard" options={iconOnlyHeader} />
        {/* Member marketplace (P2P Stage 1). headerShown:false — both screens
            render their own flat ScreenHeader, and the native stack header
            would stack a second bar on top of it. */}
        <Stack.Screen name="listings" options={{ headerShown: false }} />
        <Stack.Screen name="listing/[id]" options={{ headerShown: false }} />
        <Stack.Screen name="offers" options={{ headerShown: false }} />
        {/* Favourites renders its own ScreenHeader; without this the global
            headerShown:true stacks the native bar on top of it — two headers
            and a dead gap between them. */}
        <Stack.Screen name="favorites" options={{ headerShown: false }} />
        {/* Renders its own ScreenHeader, so the navigator's must be off — without
            this it inherits the global header and the screen shows TWO stacked
            headers, each with its own back chevron and gear. Caught on the
            simulator; no gate sees it (docs/ui-playbook.md: check how a screen
            gets its header before adding one). */}
        <Stack.Screen name="tax-reporting" options={{ headerShown: false }} />
        {/* Marketplace-only selling: list without a collection item. Renders
            its own header, same as the other P2P screens. */}
        <Stack.Screen name="sell/new" options={{ headerShown: false }} />
        {/* Same as sell/new: the screen renders its own ScreenHeader, so the
            native one would stack a SECOND header above it. Caught on the
            simulator 2026-08-08 — the route rendered a back+gear bar and
            "Choose an item" underneath it. */}
        <Stack.Screen name="sell/pick" options={{ headerShown: false }} />
        <Stack.Screen name="legal/marketplace-terms" options={{ headerShown: false }} />
        <Stack.Screen name="purchase/index" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/create-mandate" options={iconOnlyHeader} />
        <Stack.Screen name="purchase/deal/[dealId]" options={iconOnlyHeader} />

        {/* Deal Desk / P2P Selling / Marketplace */}
        <Stack.Screen name="sell/dashboard" options={iconOnlyHeader} />

        {/* Subscription & Security */}
        <Stack.Screen name="subscription" options={iconOnlyHeader} />
        <Stack.Screen name="mfa-setup" options={iconOnlyHeader} />

        {/* Additional screens */}
        {/* `notifications` was never registered here, so it fell through to the
            bare <Stack> screenOptions instead of the iconOnlyHeader every other
            pushed screen gets — and its in-component <Stack.Screen options> did
            not apply either (no "Notifications" title, no "Mark All Read"
            action rendered). Registering it makes its header identical to
            `alerts`, which sits one line above and behaves correctly. */}
        {/* Retired screen kept as a Redirect to /notifications; headerShown
            false so the stub never flashes a header on its way through. */}
        <Stack.Screen name="alerts" options={{ headerShown: false }} />
        <Stack.Screen name="notifications" options={iconOnlyHeader} />
        <Stack.Screen name="condition-guide" options={iconOnlyHeader} />
        <Stack.Screen name="leaderboard" options={iconOnlyHeader} />
        <Stack.Screen name="sets-to-complete" options={iconOnlyHeader} />
        {/* iconOnlyHeader, so back routes through safeGoBack — a guide is
            reachable by deep link, where router.back() is a silent no-op. */}
        <Stack.Screen name="guide/[categoryId]" options={iconOnlyHeader} />
        {/* Help — the "how do I use the app" pair. Same iconOnlyHeader as the
            collecting guide, so both get the safeGoBack-backed chevron: these
            are the two screens most likely to be opened from a deep link with
            nothing beneath them on the stack. */}
        <Stack.Screen name="help/index" options={iconOnlyHeader} />
        <Stack.Screen name="help/[topicId]" options={iconOnlyHeader} />
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
