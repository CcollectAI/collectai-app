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
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import { QuickNavBar } from '@/components/QuickNavBar';
import ScreenHeader from '@/components/ScreenHeader';
import { useTranslation } from 'react-i18next';
import { EmptyState } from '@/components/EmptyState';
import { userErrorMessage } from '@/lib/userErrorMessage';

type BlockedUser = { id: string; name: string };

function BlockedUsersScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const [blockedUsers, setBlockedUsers] = useState<BlockedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [unblockingId, setUnblockingId] = useState<string | null>(null);
  // A failed load is its own state. Without it the list stayed [] and rendered
  // "No blocked users" — on a SAFETY screen, telling someone nobody is blocked
  // when we simply could not ask (the favourites bug, 2026-09-13).
  const [loadFailed, setLoadFailed] = useState(false);

  const loadBlockedUsers = useCallback(async () => {
    try {
      const users = await dataProvider.listBlockedUsers();
      setBlockedUsers(users);
      setLoadFailed(false);
    } catch (err) {
      logger.error('[BlockedUsers] loadBlockedUsers error:', err);
      setLoadFailed(true);
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
              showToast({ message: userErrorMessage(err, 'Failed to unblock user.', 'BlockedUsers'), type: 'error' });
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
    // No 'top' edge: ScreenHeader applies insets.top itself, so keeping it would
    // pad the status bar twice (same note as app/favorites.tsx).
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      {/* The shared flat header, not a hand-rolled one. This screen was not
          registered in app/_layout.tsx, so it inherited the global native
          header AND drew its own centred "‹ Blocked Users" row beneath it —
          two stacked headers, two back buttons (seen on Android 2026-09-13).
          The same bug docs/ui-playbook.md records for favorites. Registered
          with headerShown: false now. */}
      <ScreenHeader title={t('screen_titles.blocked_users', { defaultValue: 'Blocked users' })} />

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
            loadFailed ? (
              <EmptyState
                icon="cloud-offline-outline"
                title={t('account.blocked_load_failed', { defaultValue: "Couldn't load your blocked users" })}
                subtitle={t('account.blocked_load_failed_hint', { defaultValue: 'Nobody has been unblocked — we just could not reach the list.' })}
                colors={colors}
                action={
                  <AnimatedPressable
                    onPress={onRefresh}
                    style={[styles.retryBtn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel={t('common.try_again', { defaultValue: 'Try again' })}
                  >
                    <Text style={[styles.retryText, { color: colors.accentText }]}>
                      {t('common.try_again', { defaultValue: 'Try again' })}
                    </Text>
                  </AnimatedPressable>
                }
              />
            ) : (
              <View style={styles.emptyContainer}>
                <Ionicons name="shield-checkmark-outline" size={64} color={colors.muted} />
                <Text style={[styles.emptyTitle, { color: colors.text }]}>
                  {t('account.blocked_empty', { defaultValue: 'No blocked users' })}
                </Text>
                <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                  {t('account.blocked_empty_hint', { defaultValue: "You haven't blocked anyone. Blocked users can't send you messages." })}
                </Text>
              </View>
            )
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
  retryBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 999, minHeight: 44, justifyContent: 'center' },
  retryText: { fontSize: 14, fontWeight: '700' },
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
