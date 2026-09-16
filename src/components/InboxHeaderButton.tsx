/**
 * InboxHeaderButton — Global inbox icon with unread badge.
 * Shows unread count from DM threads + pending requests.
 * Navigates to /inbox when pressed.
 */

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';
import { useAppTheme } from '@/hooks/useAppTheme';
import { MESSAGING_ENABLED } from '@/config/featureFlags';
import { useAuthContext } from '@/providers/useAuthContext';
import { createSharedCount } from '@/lib/sharedCount';

/**
 * ONE count for every mounted inbox button. This used to fetch per instance and
 * poll every 30s per instance — and the cluster is mounted on five tabs plus
 * every stacked screen, so an idle member paid for it several times over
 * (Diagnostics, 2026-09-14: nine chat_dm_requests_v1 timeouts in three
 * seconds). Each mount still ticks, but only a stale shared value fetches.
 */
const INBOX_POLL_MS = 30_000;
const inboxCount = createSharedCount(
  () => dataProvider.getInboxUnreadCount(),
  INBOX_POLL_MS,
  (err) => logger.error('[InboxHeaderButton] Failed to fetch unread count:', err),
);

type Props = {
  /** Icon color — falls back to theme text color */
  color?: string;
  /** Icon size, defaults to 24 */
  size?: number;
  /**
   * We are already ON /inbox. Tapping then pushed a SECOND inbox — the same
   * defect the gear had on Settings (found on Android 2026-09-09): identical
   * screen, so the tap reads as a no-op while the back stack grows. Marked
   * selected and inert instead of hidden, so the cluster keeps its shape.
   */
  active?: boolean;
};

export const InboxHeaderButton: React.FC<Props> = ({
  color,
  size = 24,
  active = false,
}) => {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const iconColor = color ?? colors.text;
  const router = useRouter();
  const { user } = useAuthContext();
  const userId = user?.id ?? null;
  const [unreadCount, setUnreadCount] = useState<number>(() => inboxCount.peek(userId));

  useEffect(() => {
    if (!MESSAGING_ENABLED) return;
    const unsubscribe = inboxCount.subscribe(setUnreadCount);
    setUnreadCount(inboxCount.peek(userId));
    void inboxCount.refreshIfStale(userId);
    // Every mount ticks; the shared count decides whether a tick fetches.
    const interval = setInterval(() => { void inboxCount.refreshIfStale(userId); }, INBOX_POLL_MS);
    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, [userId]);

  // Gated on MESSAGING_ENABLED, not on COMMUNITY_GATED (2026-08-20). The old
  // reuse hid this icon whenever the inbox was empty, so the header cluster
  // changed shape from screen to screen and the gear drifted off the edge —
  // see the flag's comment in src/config/featureFlags.ts for both defects.
  if (!MESSAGING_ENABLED) {
    return null;
  }

  return (
    <AnimatedPressable
      onPress={() => {
        if (active) return;
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        router.push('/inbox');
      }}
      style={styles.container}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={`${t('common.inbox_a11y')}${unreadCount > 0 ? `, ${t('common.unread_count_a11y', { count: unreadCount })}` : ''}`}
    >
      <Ionicons name="chatbubble-ellipses-outline" size={size} color={iconColor} />
      {unreadCount > 0 && (
        <View style={[styles.badge, { backgroundColor: colors.danger }]}>
          <Text style={styles.badgeText}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </Text>
        </View>
      )}
    </AnimatedPressable>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    padding: 4,
  },
  badge: {
    position: 'absolute',
    top: 0,
    right: 0,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#ffffff',
  },
});

export default InboxHeaderButton;
