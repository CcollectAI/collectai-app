/**
 * HeaderActions — the ONE top-right cluster: notifications · messages · settings.
 *
 * WHY THIS EXISTS (2026-08-20)
 *
 * Reported as *"top right on portfolio there's a settings icon, notification
 * icon and profile icon. this should be the same for every screen across the
 * nav bar… this is not the case currently."* An audit of the five tabs found
 * four different clusters:
 *
 *   | tab       | bell | bubble | avatar | gear |
 *   | Portfolio |  ✓   |   ✓    |   ✓    |  ✓   |
 *   | Items     |  —   |   ✓    |   ✓    |  ✓   |
 *   | Add       |  —   |   ✓    |   ✓    |  ✓   |
 *   | Events    |  —   |   ✓    |   ✓    |  ✓   |
 *   | Market    |  —   |   —    |   —    |  —   |
 *   | Explore   |  —   |   —    |   —    |  —   |
 *
 * Six files hand-rolled the same row, which is exactly how they drifted. One
 * component, one order, every screen — the same fix the tab LABEL needed when
 * three components each rendered their own copy of the bar.
 *
 * THREE ICONS, AND NO AVATAR
 *
 * The bell, the bubble and the gear are things you DO. A profile is something
 * you ARE, and mixing them is what turns a cluster into a toolbar — four icons
 * is where it stops scanning as a group. Identity lives at the TOP OF SETTINGS
 * instead (the Apple-ID-row pattern), which is one tap from a gear that is now
 * on every screen.
 *
 * That is deliberately NOT the Uber-rider mistake of burying it: Uber hides the
 * rider rating under Settings → Privacy → Privacy Center and it took press
 * coverage to make it findable. A labelled identity row at the top of the first
 * settings screen is the opposite of a fourth-level menu.
 *
 * LAYOUT
 *
 * Symmetric padding only — iOS 26 draws a translucent capsule around each bar
 * button sized to its frame, and any margin offset slides the glyph inside that
 * circle (docs/ui-playbook.md). No `marginRight` tweaks here.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useAuthContext } from '@/providers/useAuthContext';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { getNotificationHistory } from '@/api/notificationsApi';
import { logger } from '@/lib/logger';
import { createSharedCount } from '@/lib/sharedCount';

/**
 * One shared count for every mounted cluster. Module scope on purpose: two
 * headers can be mounted at once (a tab under a pushed screen), and they
 * should not each pay for the same number.
 */
const UNREAD_TTL_MS = 60_000;
// Shared, with ONE in-flight request (2026-09-14). The old cache was written
// only when a response landed, so five tab headers mounting together sent five
// requests before any of them could fill it — see src/lib/sharedCount.ts.
const notificationCount = createSharedCount(
  () => getNotificationHistory({ limit: 1, offset: 0 }).then((d) => d.unread_count),
  UNREAD_TTL_MS,
  // error, not warn: warn is stripped in release builds.
  (err) => logger.error('[HeaderActions] notification count failed:', err),
);

type Props = {
  /** Glyph size. 22 matches every existing header; the root stack passes none. */
  size?: number;
  /** Overrides the theme tint — the camera header is black in both themes. */
  color?: string;
};

export const HeaderActions: React.FC<Props> = ({ size = 22, color }) => {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const tint = color ?? colors.text;

  // The badge count used to live in `app/(tabs)/index.tsx`, which is why the
  // bell existed on exactly one screen. It belongs to the control, not to a
  // screen that happens to render it.
  //
  // CACHED ACROSS INSTANCES, deliberately. Moving the fetch into the cluster
  // multiplied it: this component now mounts on five tabs plus every one of
  // the 15 screens that use `ScreenHeader`, so a naive per-mount fetch would
  // turn one request per session into one per screen you open. The count is
  // a badge, not a number anyone acts on to the second — a 60s TTL keeps it
  // honest and costs one request a minute at worst.
  // (CLAUDE.md: measure the cost you add rather than assuming it is small.)
  const { user } = useAuthContext();
  // Whose count is held matters as much as how old it is: module scope survives
  // a sign-out, so the shared count is keyed by user id.
  const userId = user?.id ?? null;
  const [unread, setUnread] = useState(() => notificationCount.peek(userId));
  useEffect(() => {
    const unsubscribe = notificationCount.subscribe(setUnread);
    setUnread(notificationCount.peek(userId));
    void notificationCount.refreshIfStale(userId);
    return unsubscribe;
  }, [userId]);

  // The cluster is on EVERY screen, including the three screens it navigates
  // to — so on Settings the gear pushed **another copy of Settings**. Found on
  // Android 2026-09-09: the tap looked like a no-op (the new screen is
  // identical), and it took TWO back presses to leave. A control that silently
  // deepens the stack is worse than one that does nothing.
  //
  // The icon stays rendered, tinted and marked selected, rather than being
  // hidden: this component exists because clusters that change shape from
  // screen to screen were the original complaint (see the header). This is the
  // tab-bar convention — the control for where you already are is a state
  // indicator, not a dead button.
  const pathname = usePathname();
  const isHere = useCallback(
    (path: string) => pathname === path || pathname.startsWith(`${path}/`),
    [pathname],
  );

  const go = useCallback((path: '/notifications' | '/settings') => {
    if (isHere(path)) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(path);
  }, [router, settings.hapticsEnabled, isHere]);

  return (
    <View style={styles.row}>
      <AnimatedPressable
        onPress={() => go('/notifications')}
        style={styles.iconBtn}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityState={{ selected: isHere('/notifications') }}
        accessibilityLabel={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
      >
        <Ionicons
          name="notifications-outline"
          size={size}
          color={isHere('/notifications') ? colors.accent : tint}
        />
        {unread > 0 && (
          <View style={[styles.badge, { backgroundColor: colors.error }]}>
            <Text style={[styles.badgeText, { color: colors.accentText }]}>
              {unread > 99 ? '99+' : unread}
            </Text>
          </View>
        )}
      </AnimatedPressable>

      <InboxHeaderButton
        color={isHere('/inbox') ? colors.accent : tint}
        size={size}
        active={isHere('/inbox')}
      />

      <AnimatedPressable
        testID="open-settings-btn"
        onPress={() => go('/settings')}
        style={styles.iconBtn}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityState={{ selected: isHere('/settings') }}
        accessibilityLabel="Settings"
      >
        <Ionicons
          name="settings-outline"
          size={size}
          color={isHere('/settings') ? colors.accent : tint}
        />
      </AnimatedPressable>
    </View>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  // Symmetric on all four sides — see the iOS 26 capsule note in the header.
  iconBtn: { padding: 8 },
  badge: {
    position: 'absolute', top: 2, right: 2,
    minWidth: 16, height: 16, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3,
  },
  badgeText: { fontSize: 10, fontWeight: '700' },
});

export default HeaderActions;
