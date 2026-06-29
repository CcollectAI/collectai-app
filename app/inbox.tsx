/**
 * Inbox Screen — WhatsApp-style DM inbox with requests inline.
 * Shows pending DM requests at top, sent requests, then accepted message threads.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  Alert,
  Animated,
} from 'react-native';
import { Image } from 'expo-image';
import { useToast } from '@/components/Toast';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type DmThread, type DmRequest } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { SkeletonList } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import logger from '@/utils/logger';
import { logAuthState, logLoad, startTimer } from '@/utils/diagnostics';
import { QuickNavBar } from '@/components/QuickNavBar';
import { timeAgoShort } from '@/lib/timeAgo';
import { MS_PER_WEEK } from '@/constants/time';
import { radius, text, fontWeight } from '@/theme/tokens';
import { supabase } from '@/lib/supabase';
import { trackScreen } from '@/analytics/track';


function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const diff = Date.now() - date.getTime();
  if (diff < MS_PER_WEEK) return timeAgoShort(date);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const UserAvatar = React.memo(function UserAvatar({
  name,
  avatarUrl,
  avatarColor,
  size = 48,
}: {
  name: string;
  avatarUrl?: string | null;
  avatarColor?: string;
  size?: number;
}) {
  const { colors } = useAppTheme();
  const initials = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  if (avatarUrl) {
    return (
      <Image
        source={{ uri: avatarUrl }}
        style={{
          width: size,
          height: size,
          borderRadius: size / 2,
        }}
        accessibilityLabel={`${name} avatar`}
        cachePolicy="memory-disk"
      />
    );
  }

  return (
    <View
      style={[
        styles.avatar,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: avatarColor || colors.muted,
        },
      ]}
    >
      <Text style={[styles.avatarText, { fontSize: size * 0.4 }]}>{initials}</Text>
    </View>
  );
});

function InboxScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [threads, setThreads] = useState<DmThread[]>([]);
  const [sentRequests, setSentRequests] = useState<DmThread[]>([]);
  const [requests, setRequests] = useState<DmRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processingRequestId, setProcessingRequestId] = useState<string | null>(null);

  const loadInbox = useCallback(async () => {
    const elapsed = startTimer();
    logAuthState('inbox');
    try {
      const [inboxThreads, incomingRequests] = await Promise.all([
        dataProvider.listInboxThreads(),
        dataProvider.listIncomingRequests(),
      ]);

      // Separate accepted threads from pending outgoing (sent requests)
      const accepted = inboxThreads.filter((t) => t.status === 'accepted');
      const pending = inboxThreads.filter((t) => t.status === 'pending' && !t.isIncoming);

      setThreads(accepted);
      setSentRequests(pending);
      setRequests(incomingRequests);
      logLoad('inbox', {
        threads: inboxThreads.length,
        accepted: accepted.length,
        requests: incomingRequests.length,
        ms: elapsed(),
      });
    } catch (err) {
      logLoad('inbox', { error: err instanceof Error ? err.message : String(err), ms: elapsed() });
      logger.warn('[InboxScreen] loadInbox error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Analytics: track screen on mount
  useEffect(() => {
    trackScreen('inbox');
  }, []);

  // Initial load
  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  // Supabase Realtime: refresh threads on new DM messages
  useEffect(() => {
    const channel = supabase.channel('inbox-updates')
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'dm_messages',
      }, () => {
        loadInbox();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [loadInbox]);

  // Refresh threads when screen regains focus (e.g. returning from a thread)
  useFocusEffect(
    useCallback(() => {
      loadInbox();
    }, [loadInbox])
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadInbox();
  }, [loadInbox]);

  const handleAcceptRequest = async (threadId: string) => {
    setProcessingRequestId(threadId);
    try {
      await dataProvider.decideDmRequest(threadId, true);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      await loadInbox();
    } catch (err: unknown) {
      showToast({ message: err instanceof Error ? err.message : 'Failed to accept request', type: 'error' });
    } finally {
      setProcessingRequestId(null);
    }
  };

  const handleDeclineRequest = async (threadId: string) => {
    Alert.alert(
      'Decline Request',
      'Are you sure you want to decline this message request?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Decline',
          style: 'destructive',
          onPress: async () => {
            setProcessingRequestId(threadId);
            try {
              await dataProvider.decideDmRequest(threadId, false);
              await loadInbox();
            } catch (err: unknown) {
              showToast({ message: err instanceof Error ? err.message : 'Failed to decline request', type: 'error' });
            } finally {
              setProcessingRequestId(null);
            }
          },
        },
      ]
    );
  };

  const handleBlockFromRequest = async (req: DmRequest) => {
    Alert.alert(
      'Block User',
      `Block ${req.fromUserName}? This will also decline their request. You can unblock them later in Settings.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Block',
          style: 'destructive',
          onPress: async () => {
            setProcessingRequestId(req.threadId);
            try {
              await Promise.all([
                dataProvider.blockUser(req.fromUserId),
                dataProvider.decideDmRequest(req.threadId, false),
              ]);
              fireHaptic(HapticIntent.ALERT_TRIGGERED);
              await loadInbox();
            } catch (err: unknown) {
              showToast({ message: err instanceof Error ? err.message : 'Failed to block user', type: 'error' });
            } finally {
              setProcessingRequestId(null);
            }
          },
        },
      ]
    );
  };

  const handleThreadPress = (thread: DmThread) => {
    // Mark as read (best-effort)
    dataProvider.markThreadRead(thread.id).catch((err) => {
      logger.warn('[InboxScreen] markThreadRead error:', err);
    });

    // Navigate to thread detail
    router.push(`/chat/${thread.id}`);
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Inbox</Text>
          <View style={{ width: 32 }} />
        </View>
        <View style={styles.loadingContainer}>
          <SkeletonList count={5} type="row" />
        </View>
      </SafeAreaView>
    );
  }

  const hasContent = requests.length > 0 || threads.length > 0 || sentRequests.length > 0;

  // Total unread count across all threads
  const totalUnread = threads.reduce((sum, t) => sum + (t.unreadCount ?? 0), 0) + requests.length;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <View style={styles.headerTitleRow}>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Inbox</Text>
          {totalUnread > 0 && (
            <View style={[styles.headerUnreadBadge, { backgroundColor: colors.accent }]}>
              <Text style={styles.headerUnreadText}>{totalUnread > 99 ? '99+' : totalUnread}</Text>
            </View>
          )}
        </View>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.accent}
          />
        }
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
        {/* Requests Section - Highlighted with accent theme */}
        {requests.length > 0 && (
          <View style={styles.section}>
            <View style={[styles.sectionTitleHighlight, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="mail-unread-outline" size={16} color={colors.accent} style={{ marginRight: 6 }} />
              <Text style={[styles.sectionTitleText, { color: colors.text }]}>
                Message Requests ({requests.length})
              </Text>
            </View>
            {requests.map((req) => (
              <View key={req.threadId} style={[styles.requestCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <View style={styles.requestHeader}>
                  <UserAvatar
                    name={req.fromUserName}
                    avatarUrl={req.fromUserAvatarUrl}
                    avatarColor={req.fromUserAvatarColor}
                    size={44}
                  />
                  <View style={styles.requestInfo}>
                    <Text style={[styles.requestName, { color: colors.text }]}>{req.fromUserName}</Text>
                    {req.fromUserHandle && (
                      <Text style={[styles.requestHandle, { color: colors.muted }]}>@{req.fromUserHandle}</Text>
                    )}
                    <Text style={[styles.requestTime, { color: colors.muted }]}>
                      {formatRelativeTime(req.requestedAt)}
                    </Text>
                  </View>
                </View>
                {req.requestMessage && (
                  <View style={[styles.requestMessageWrap, { backgroundColor: colors.background }]}>
                    <Ionicons name="chatbubble-outline" size={14} color={colors.muted} style={{ marginRight: 8 }} />
                    <Text style={[styles.requestMessage, { color: colors.text }]} numberOfLines={2}>
                      &quot;{req.requestMessage}&quot;
                    </Text>
                  </View>
                )}
                <View style={styles.requestActions}>
                  <AnimatedPressable
                    style={[styles.actionBtn, styles.acceptBtn, { backgroundColor: colors.accent }]}
                    onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleAcceptRequest(req.threadId); }}
                    disabled={processingRequestId === req.threadId}
                    accessibilityRole="button"
                    accessibilityLabel={`Accept message request from ${req.fromUserName}`}
                  >
                    {processingRequestId === req.threadId ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={styles.acceptBtnText}>Accept</Text>
                    )}
                  </AnimatedPressable>
                  <AnimatedPressable
                    style={[styles.actionBtn, styles.declineBtn, { backgroundColor: colors.danger + '15', borderColor: colors.danger + '40' }]}
                    onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); handleDeclineRequest(req.threadId); }}
                    disabled={processingRequestId === req.threadId}
                    accessibilityRole="button"
                    accessibilityLabel={`Decline message request from ${req.fromUserName}`}
                  >
                    {processingRequestId === req.threadId ? (
                      <ActivityIndicator size="small" color={colors.danger} />
                    ) : (
                      <Text style={[styles.declineBtnText, { color: colors.danger }]}>Decline</Text>
                    )}
                  </AnimatedPressable>
                  <AnimatedPressable
                    style={[styles.blockBtn, { backgroundColor: colors.danger + '10' }]}
                    onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); handleBlockFromRequest(req); }}
                    disabled={processingRequestId === req.threadId}
                    accessibilityRole="button"
                    accessibilityLabel={`Block ${req.fromUserName}`}
                  >
                    <Text style={[styles.blockBtnText, { color: colors.danger }]}>Block</Text>
                  </AnimatedPressable>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Messages Section */}
        {threads.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]}>Messages</Text>
            {threads.map((thread, idx) => (
              <AnimatedPressable
                key={thread.id}
                style={[
                  styles.threadRow,
                  idx < threads.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
                ]}
                onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); handleThreadPress(thread); }}
                accessibilityRole="button"
                accessibilityLabel={`Message thread with ${thread.otherUserName}${thread.unreadCount > 0 ? `, ${thread.unreadCount} unread` : ''}`}
              >
                <UserAvatar
                  name={thread.otherUserName}
                  avatarUrl={thread.otherUserAvatarUrl}
                  avatarColor={thread.otherUserAvatarColor}
                  size={52}
                />
                <View style={styles.threadContent}>
                  <View style={styles.threadHeader}>
                    <Text
                      style={[
                        styles.threadName,
                        { color: colors.text },
                        thread.unreadCount > 0 && styles.threadNameUnread,
                      ]}
                    >
                      {thread.otherUserName}
                    </Text>
                    <Text style={[styles.threadTime, { color: colors.muted }]}>
                      {formatRelativeTime(thread.lastMessageAt)}
                    </Text>
                  </View>
                  <View style={styles.threadPreviewRow}>
                    <Text
                      style={[
                        styles.threadPreview,
                        { color: colors.muted },
                        thread.unreadCount > 0 && { color: colors.text, fontWeight: fontWeight.medium },
                      ]}
                      numberOfLines={1}
                    >
                      {thread.lastMessagePreview || 'No messages yet'}
                    </Text>
                    {thread.unreadCount > 0 && (
                      <View style={[styles.unreadBadge, { backgroundColor: colors.accent }]}>
                        <Text style={styles.unreadBadgeText}>
                          {thread.unreadCount > 99 ? '99+' : thread.unreadCount}
                        </Text>
                      </View>
                    )}
                  </View>
                </View>
              </AnimatedPressable>
            ))}
          </View>
        )}

        {/* Sent Requests Section */}
        {sentRequests.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]}>Sent Requests</Text>
            {sentRequests.map((thread, idx) => (
              <View
                key={thread.id}
                style={[
                  styles.threadRow,
                  idx < sentRequests.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
                ]}
              >
                <UserAvatar
                  name={thread.otherUserName}
                  avatarUrl={thread.otherUserAvatarUrl}
                  avatarColor={thread.otherUserAvatarColor}
                  size={52}
                />
                <View style={styles.threadContent}>
                  <View style={styles.threadHeader}>
                    <Text style={[styles.threadName, { color: colors.text }]}>
                      {thread.otherUserName}
                    </Text>
                    <View style={[styles.pendingBadge, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.pendingBadgeText, { color: colors.accent }]}>Pending</Text>
                    </View>
                  </View>
                  <Text
                    style={[styles.threadPreview, { color: colors.muted }]}
                    numberOfLines={1}
                  >
                    {thread.lastMessagePreview || 'Awaiting response'}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Empty State */}
        {!hasContent && (
          <EmptyState
            icon="chatbubbles-outline"
            title="No messages yet"
            subtitle="Start a conversation by visiting someone's profile"
            colors={colors}
            style={{ paddingTop: 80 }}
          />
        )}
        </Animated.View>
      </ScrollView>
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
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerUnreadBadge: {
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  headerUnreadText: {
    fontSize: text.xs,
    fontWeight: fontWeight.bold,
    color: '#ffffff',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  section: {
    marginTop: 16,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  sectionTitleHighlight: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.sm,
    marginBottom: 12,
  },
  sectionTitleText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // Request cards
  requestCard: {
    borderRadius: radius.md,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
  },
  requestHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  requestInfo: {
    marginLeft: 12,
    flex: 1,
  },
  requestName: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  requestHandle: {
    fontSize: text.md,
    marginTop: 1,
  },
  requestTime: {
    fontSize: text.sm,
    marginTop: 2,
  },
  requestMessageWrap: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 12,
    padding: 12,
    borderRadius: radius.sm,
  },
  requestMessage: {
    flex: 1,
    fontSize: text.md,
    lineHeight: 20,
    fontStyle: 'italic',
  },
  requestActions: {
    flexDirection: 'row',
    marginTop: 16,
    gap: 12,
    alignItems: 'center',
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  declineBtn: {
    borderWidth: 1,
  },
  declineBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  acceptBtn: {
    // backgroundColor applied inline
  },
  acceptBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    color: '#ffffff',
  },
  blockBtn: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  blockBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // Thread rows — cleaner WhatsApp-style
  threadRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 0,
    marginBottom: 0,
  },
  avatar: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontWeight: fontWeight.bold,
    color: '#ffffff',
  },
  threadContent: {
    flex: 1,
    marginLeft: 12,
  },
  threadHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  threadName: {
    fontSize: text.lg,
    fontWeight: fontWeight.medium,
  },
  threadNameUnread: {
    fontWeight: fontWeight.bold,
  },
  threadTime: {
    fontSize: text.sm,
  },
  threadPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  threadPreview: {
    flex: 1,
    fontSize: text.md,
  },
  unreadBadge: {
    minWidth: 20,
    height: 20,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
    marginLeft: 8,
  },
  unreadBadgeText: {
    fontSize: text.xs,
    fontWeight: fontWeight.bold,
    color: '#ffffff',
  },
  pendingBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  pendingBadgeText: {
    fontSize: text.xs,
    fontWeight: fontWeight.semibold,
  },

});

export default function InboxScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Inbox">
      <InboxScreen />
    </ScreenErrorBoundary>
  );
}
