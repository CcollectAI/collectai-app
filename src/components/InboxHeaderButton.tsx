/**
 * InboxHeaderButton — Global inbox icon with unread badge.
 * Shows unread count from DM threads + pending requests.
 * Navigates to /inbox when pressed.
 */

import React, { useEffect, useState } from 'react';
import { TouchableOpacity, View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';

type Props = {
  /** Icon color, defaults to navy */
  color?: string;
  /** Icon size, defaults to 24 */
  size?: number;
};

export const InboxHeaderButton: React.FC<Props> = ({
  color = '#0B1F3A',
  size = 24,
}) => {
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
        console.warn('[InboxHeaderButton] Failed to fetch unread count:', err);
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
    <TouchableOpacity
      onPress={() => router.push('/inbox')}
      style={styles.container}
      accessibilityRole="button"
      accessibilityLabel={`Inbox${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
    >
      <Ionicons name="chatbubble-ellipses-outline" size={size} color={color} />
      {unreadCount > 0 && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </Text>
        </View>
      )}
    </TouchableOpacity>
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
    backgroundColor: '#ef4444',
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
