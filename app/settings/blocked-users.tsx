/**
 * Blocked Users Screen — manage blocked users list.
 * Accessible from Settings > Blocked Users.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import { QuickNavBar } from '@/components/QuickNavBar';
import { safeGoBack } from '@/lib/goBack';

type BlockedUser = { id: string; name: string };

function BlockedUsersScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const [blockedUsers, setBlockedUsers] = useState<BlockedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [unblockingId, setUnblockingId] = useState<string | null>(null);

  const loadBlockedUsers = useCallback(async () => {
    try {
      const users = await dataProvider.listBlockedUsers();
      setBlockedUsers(users);
    } catch (err) {
      logger.error('[BlockedUsers] loadBlockedUsers error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadBlockedUsers();
  }, [loadBlockedUsers]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadBlockedUsers();
  }, [loadBlockedUsers]);

  const handleUnblock = (user: BlockedUser) => {
    Alert.alert(
      'Unblock User',
      `Unblock ${user.name}? They will be able to send you messages again.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Unblock',
          onPress: async () => {
            setUnblockingId(user.id);
            try {
              await dataProvider.unblockUser(user.id);
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              setBlockedUsers((prev) => prev.filter((u) => u.id !== user.id));
            } catch (err: unknown) {
              showToast({ message: err instanceof Error ? err.message : 'Failed to unblock user.', type: 'error' });
            } finally {
              setUnblockingId(null);
            }
          },
        },
      ],
    );
  };

  const renderItem = ({ item }: { item: BlockedUser }) => {
    const initials = item.name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);

    return (
      <View style={[styles.userRow, { borderBottomColor: colors.border }]}>
        <View style={[styles.avatar, { backgroundColor: colors.muted }]}>
          <Text style={styles.avatarText}>{initials}</Text>
        </View>
        <Text style={[styles.userName, { color: colors.text }]} numberOfLines={1}>
          {item.name}
        </Text>
        <AnimatedPressable
          style={[styles.unblockBtn, { borderColor: colors.accent }]}
          onPress={() => handleUnblock(item)}
          disabled={unblockingId === item.id}
          accessibilityRole="button"
          accessibilityLabel={`Unblock ${item.name}`}
        >
          {unblockingId === item.id ? (
            <ActivityIndicator size="small" color={colors.accent} />
          ) : (
            <Text style={[styles.unblockBtnText, { color: colors.accent }]}>Unblock</Text>
          )}
        </AnimatedPressable>
      </View>
    );
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); safeGoBack(router); }}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Blocked Users</Text>
        <View style={{ width: 32 }} />
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={blockedUsers}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={blockedUsers.length === 0 ? styles.emptyListContent : styles.listContent}
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="shield-checkmark-outline" size={64} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                No blocked users
              </Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                You haven&apos;t blocked anyone. Blocked users can&apos;t send you messages.
              </Text>
            </View>
          }
        />
      )}
      <QuickNavBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 32,
  },
  emptyListContent: {
    flexGrow: 1,
  },
  userRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  userName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '500',
    marginLeft: 12,
  },
  unblockBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 80,
    alignItems: 'center',
  },
  unblockBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingTop: 80,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
});

export default function BlockedUsersScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Blocked Users">
      <BlockedUsersScreen />
    </ScreenErrorBoundary>
  );
}
