/**
 * Inbox Screen — WhatsApp-style DM inbox with requests inline.
 * Shows pending DM requests at top, followed by accepted message threads.
 */

import React, { useEffect, useState, useCallback } from 'react';
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
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type DmThread, type DmRequest } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';

// Semantic color fallback — used in the static StyleSheet where hooks are not accessible.
// Inside the component, prefer `colors.danger` from the theme instead.
const FALLBACK_ERROR = '#ef4444';

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';

  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}d`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function UserAvatar({
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
  const initials = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <View
      style={[
        styles.avatar,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: avatarColor || '#6b7280',
        },
      ]}
    >
      <Text style={[styles.avatarText, { fontSize: size * 0.4 }]}>{initials}</Text>
    </View>
  );
}

export default function InboxScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const [threads, setThreads] = useState<DmThread[]>([]);
  const [requests, setRequests] = useState<DmRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processingRequestId, setProcessingRequestId] = useState<string | null>(null);

  const loadInbox = useCallback(async () => {
    try {
      const [inboxThreads, incomingRequests] = await Promise.all([
        dataProvider.listInboxThreads(),
        dataProvider.listIncomingRequests(),
      ]);
      setThreads(inboxThreads);
      setRequests(incomingRequests);
    } catch (err) {
      logger.warn('[InboxScreen] loadInbox error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadInbox();
  }, [loadInbox]);

  const handleAcceptRequest = async (threadId: string) => {
    setProcessingRequestId(threadId);
    try {
      await dataProvider.decideDmRequest(threadId, true);
      // Reload to show thread in messages
      await loadInbox();
    } catch (err: unknown) {
      Alert.alert('Error', err?.message || 'Failed to accept request');
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
              Alert.alert('Error', err?.message || 'Failed to decline request');
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
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  const hasContent = requests.length > 0 || threads.length > 0;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Inbox</Text>
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
                      "{req.requestMessage}"
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
                    style={[styles.actionBtn, styles.declineBtn]}
                    onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); handleDeclineRequest(req.threadId); }}
                    disabled={processingRequestId === req.threadId}
                    accessibilityRole="button"
                    accessibilityLabel={`Decline message request from ${req.fromUserName}`}
                  >
                    {processingRequestId === req.threadId ? (
                      <ActivityIndicator size="small" color={colors.danger ?? FALLBACK_ERROR} />
                    ) : (
                      <Text style={styles.declineBtnText}>Decline</Text>
                    )}
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
                        thread.unreadCount > 0 && { color: colors.text, fontWeight: '500' },
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

        {/* Empty State */}
        {!hasContent && (
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={64} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No messages yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Start a conversation by visiting someone's profile
            </Text>
          </View>
        )}
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

// Static styles only — no theme tokens
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
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  sectionTitleHighlight: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    marginBottom: 12,
  },
  sectionTitleText: {
    fontSize: 14,
    fontWeight: '600',
  },

  // Request cards
  requestCard: {
    borderRadius: 12,
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
    fontSize: 16,
    fontWeight: '600',
  },
  requestHandle: {
    fontSize: 13,
    marginTop: 1,
  },
  requestTime: {
    fontSize: 12,
    marginTop: 2,
  },
  requestMessageWrap: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 12,
    padding: 12,
    borderRadius: 10,
  },
  requestMessage: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
    fontStyle: 'italic',
  },
  requestActions: {
    flexDirection: 'row',
    marginTop: 16,
    gap: 12,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  declineBtn: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  declineBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: FALLBACK_ERROR,
  },
  acceptBtn: {
    // backgroundColor applied inline
  },
  acceptBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
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
    fontWeight: '700',
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
    fontSize: 15,
    fontWeight: '500',
  },
  threadNameUnread: {
    fontWeight: '700',
  },
  threadTime: {
    fontSize: 12,
  },
  threadPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  threadPreview: {
    flex: 1,
    fontSize: 14,
  },
  unreadBadge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
    marginLeft: 8,
  },
  unreadBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#ffffff',
  },

  // Empty state
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
