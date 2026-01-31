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

// Fixed colors for specific UI elements
const fixedColors = {
  error: '#ef4444',
  success: '#22c55e',
};

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
      console.warn('[InboxScreen] loadInbox error:', err);
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
    } catch (err: any) {
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
            } catch (err: any) {
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
      console.warn('[InboxScreen] markThreadRead error:', err);
    });

    // Navigate to thread detail
    router.push(`/chat/${thread.id}`);
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  const hasContent = requests.length > 0 || threads.length > 0;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
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
        <Animated.View style={animatedStyle}>
        {/* Requests Section */}
        {requests.length > 0 && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]}>
              Message Requests ({requests.length})
            </Text>
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
                  <Text style={[styles.requestMessage, { color: colors.text }]} numberOfLines={2}>
                    {req.requestMessage}
                  </Text>
                )}
                <View style={styles.requestActions}>
                  <AnimatedPressable
                    style={[styles.actionBtn, styles.declineBtn]}
                    onPress={() => handleDeclineRequest(req.threadId)}
                    disabled={processingRequestId === req.threadId}
                  >
                    {processingRequestId === req.threadId ? (
                      <ActivityIndicator size="small" color={fixedColors.error} />
                    ) : (
                      <Text style={styles.declineBtnText}>Decline</Text>
                    )}
                  </AnimatedPressable>
                  <AnimatedPressable
                    style={[styles.actionBtn, styles.acceptBtn, { backgroundColor: colors.accent }]}
                    onPress={() => handleAcceptRequest(req.threadId)}
                    disabled={processingRequestId === req.threadId}
                  >
                    {processingRequestId === req.threadId ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={styles.acceptBtnText}>Accept</Text>
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
            {threads.map((thread) => (
              <AnimatedPressable
                key={thread.id}
                style={[styles.threadRow, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => handleThreadPress(thread)}
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
            <AnimatedPressable
              style={[styles.newMessageBtn, { backgroundColor: colors.accent }]}
              onPress={() => router.push('/chat/new')}
            >
              <Ionicons name="add" size={18} color="#fff" />
              <Text style={styles.newMessageBtnText}>New Message</Text>
            </AnimatedPressable>
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
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
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
  requestMessage: {
    fontSize: 14,
    marginTop: 12,
    lineHeight: 20,
  },
  requestActions: {
    flexDirection: 'row',
    marginTop: 16,
    gap: 12,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
  },
  declineBtn: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  declineBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: fixedColors.error,
  },
  acceptBtn: {
    // backgroundColor applied inline
  },
  acceptBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
  },

  // Thread rows
  threadRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
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
  newMessageBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    marginTop: 24,
    gap: 8,
  },
  newMessageBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#ffffff',
  },
});
