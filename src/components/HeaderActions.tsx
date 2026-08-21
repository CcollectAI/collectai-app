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
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useAuthContext } from '@/providers/useAuthContext';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { getNotificationHistory } from '@/api/notificationsApi';
import { logger } from '@/lib/logger';

/**
 * One shared count for every mounted cluster. Module scope on purpose: two
 * headers can be mounted at once (a tab under a pushed screen), and they
 * should not each pay for the same number.
 */
const UNREAD_TTL_MS = 60_000;
const unreadCache = { value: 0, at: 0, userId: null as string | null };

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
  const [unread, setUnread] = useState(unreadCache.userId === user?.id ? unreadCache.value : 0);
  useEffect(() => {
    let cancelled = false;
    // Whose count is cached matters as much as how old it is: module scope
    // survives a sign-out, so without this the next account would wear the
    // previous one's badge for up to a minute.
    if (unreadCache.userId !== (user?.id ?? null)) {
      unreadCache.value = 0;
      unreadCache.at = 0;
      unreadCache.userId = user?.id ?? null;
      setUnread(0);
    }
    if (!user?.id) return;
    if (Date.now() - unreadCache.at < UNREAD_TTL_MS) {
      setUnread(unreadCache.value);
      return;
    }
    getNotificationHistory({ limit: 1, offset: 0 })
      .then((data) => {
        unreadCache.value = data.unread_count;
        unreadCache.at = Date.now();
        unreadCache.userId = user?.id ?? null;
        if (!cancelled) setUnread(data.unread_count);
      })
      .catch((err) => logger.warn('[HeaderActions] notification count failed:', err));
    return () => { cancelled = true; };
  }, [user?.id]);

  const go = useCallback((path: '/notifications' | '/settings') => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(path);
  }, [router, settings.hapticsEnabled]);

  return (
    <View style={styles.row}>
      <AnimatedPressable
        onPress={() => go('/notifications')}
        style={styles.iconBtn}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityLabel={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
      >
        <Ionicons name="notifications-outline" size={size} color={tint} />
        {unread > 0 && (
          <View style={[styles.badge, { backgroundColor: colors.error }]}>
            <Text style={[styles.badgeText, { color: colors.accentText }]}>
              {unread > 99 ? '99+' : unread}
            </Text>
          </View>
        )}
      </AnimatedPressable>

      <InboxHeaderButton color={tint} size={size} />

      <AnimatedPressable
        testID="open-settings-btn"
        onPress={() => go('/settings')}
        style={styles.iconBtn}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityLabel="Settings"
      >
        <Ionicons name="settings-outline" size={size} color={tint} />
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
