/**
 * InboxHeaderButton — Global inbox icon with unread badge.
 * Shows unread count from DM threads + pending requests.
 * Navigates to /inbox when pressed.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';
import { useAppTheme } from '@/hooks/useAppTheme';

type Props = {
  /** Icon color — falls back to theme text color */
  color?: string;
  /** Icon size, defaults to 24 */
  size?: number;
};

export const InboxHeaderButton: React.FC<Props> = ({
  color,
  size = 24,
}) => {
  const { colors } = useAppTheme();
  const iconColor = color ?? colors.text;
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  useEffect(() => {
    let mounted = true;

    const fetchUnread = async () => {
      try {
        const count = await dataProvider.getInboxUnreadCount();
        if (mounted) {
          setUnreadCount(count);
        }
      } catch (err) {
        logger.warn('[InboxHeaderButton] Failed to fetch unread count:', err);
      }
    };

    fetchUnread();

    // Poll every 30 seconds for new messages
    const interval = setInterval(fetchUnread, 30_000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        router.push('/inbox');
      }}
      style={styles.container}
      accessibilityRole="button"
      accessibilityLabel={`Inbox${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
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
