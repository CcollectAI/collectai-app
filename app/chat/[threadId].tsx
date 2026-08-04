/**
 * Thread Detail Screen — View messages + send new messages.
 * Route: /chat/[threadId]
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Image,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type DmMessage, type DmThread, type PublicUserProfile } from '@/data';
import { supabase } from '@/lib/supabase';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { SkeletonChat } from '@/components/Skeleton';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';
import { QuickNavBar } from '@/components/QuickNavBar';
import { MS_PER_DAY } from '@/constants/time';
import { radius, text, fontWeight } from '@/theme/tokens';
import { safeGoBack } from '@/lib/goBack';

// Message with local status for optimistic UI
type LocalMessage = DmMessage & {
  localStatus?: 'sending' | 'sent' | 'failed';
};

function formatDateSeparator(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const msgDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.floor((today.getTime() - msgDate.getTime()) / MS_PER_DAY);

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function shouldShowDateSeparator(current: string, previous: string | null): boolean {
  if (!previous) return true;
  const currentDate = new Date(current).toDateString();
  const previousDate = new Date(previous).toDateString();
  return currentDate !== previousDate;
}

function ThreadDetailScreen() {
  const router = useRouter();
  const { threadId } = useLocalSearchParams<{ threadId: string }>();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [threadInfo, setThreadInfo] = useState<DmThread | null>(null);
  const [currentUser, setCurrentUser] = useState<PublicUserProfile | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [otherTyping, setOtherTyping] = useState(false);
  const [failedMessageIds, setFailedMessageIds] = useState<Set<string>>(new Set());

  const flatListRef = useRef<FlatList>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingClearRef = useRef<ReturnType<typeof setTimeout> | null>(null);
   
  const presenceChannelRef = useRef<any>(null);
  const isNearBottomRef = useRef(true);

  // Current user ID (empty string fallback before profile loads)
  const currentUserId = currentUser?.id ?? '';

  // Load messages
  const loadMessages = useCallback(async () => {
    if (!threadId) return;
    try {
      const msgs = await dataProvider.getThreadMessages(threadId);
      setMessages(msgs.map((m) => ({ ...m, localStatus: 'sent' })));
    } catch (err) {
      logger.error('[ThreadDetail] loadMessages error:', err);
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  // Load thread info for header
  const loadThreadInfo = useCallback(async () => {
    if (!threadId) return;
    try {
      const threads = await dataProvider.listInboxThreads();
      const found = threads.find((t) => t.id === threadId);
      if (found) setThreadInfo(found);
    } catch (err) {
      logger.error('[ThreadDetail] loadThreadInfo error:', err);
    }
  }, [threadId]);

  // Load current user profile
  const loadCurrentUser = useCallback(async () => {
    try {
      const profile = await dataProvider.getMyProfile();
      if (profile) setCurrentUser(profile);
    } catch (err) {
      logger.error('[ThreadDetail] loadCurrentUser error:', err);
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadMessages();
    setRefreshing(false);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [loadMessages, settings.hapticsEnabled]);

  // Initial data load
  useEffect(() => {
    loadMessages();
    loadThreadInfo();
    loadCurrentUser();
  }, [loadMessages, loadThreadInfo, loadCurrentUser]);

  // Mark thread as read on mount + whenever screen regains focus
  useFocusEffect(
    useCallback(() => {
      if (!threadId) return;
      try {
        dataProvider.markThreadRead(threadId).catch((err) => logger.info('[Chat] markRead error:', err));
      } catch (e) {
        logger.error('[silent-fallback] chat: thread action failed:', e);
        // Non-critical
      }
    }, [threadId])
  );

  // Supabase Realtime subscription for new messages (replaces 8s polling)
  useEffect(() => {
    if (!threadId) return;

    const channel = supabase.channel(`thread-${threadId}`)
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'dm_messages',
        filter: `thread_id=eq.${threadId}`,
      }, (payload) => {
        const newMsg = payload.new as Record<string, unknown>;
        setMessages((prev) => {
          // Avoid duplicates (optimistic messages already in list)
          if (prev.some((m) => m.id === newMsg.id)) return prev;
          return [...prev, {
            id: newMsg.id as string,
            threadId: newMsg.thread_id as string,
            authorUserId: newMsg.author_user_id as string,
            text: newMsg.text as string,
            createdAt: newMsg.created_at as string,
            readAt: (newMsg.read_at as string) ?? null,
            localStatus: 'sent',
          }];
        });
        // Mark as read if the new message is from the other user
        if (newMsg.author_user_id !== currentUserId) {
          dataProvider.markThreadRead(threadId).catch((err) => logger.info('[Chat] markRead error:', err));
        }
      })
      .on('postgres_changes', {
        event: 'UPDATE',
        schema: 'public',
        table: 'dm_messages',
        filter: `thread_id=eq.${threadId}`,
      }, (payload) => {
        // Sync read receipts when messages are updated (e.g. read_at set)
        const updated = payload.new as Record<string, unknown>;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === updated.id
              ? { ...m, readAt: (updated.read_at as string) ?? m.readAt }
              : m
          )
        );
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [threadId, currentUserId]);

  // Realtime presence for typing indicators (replaces polling)
  useEffect(() => {
    if (!threadId || !currentUserId) return;

    const presenceChannel = supabase.channel(`typing-${threadId}`, {
      config: { presence: { key: currentUserId } },
    });

    presenceChannel
      .on('presence', { event: 'sync' }, () => {
        const state = presenceChannel.presenceState();
        // Check if any user other than us is typing
        const otherUsers = Object.keys(state).filter((key) => key !== currentUserId);
        const anyoneTyping = otherUsers.some((key) => {
          const presences = state[key] as { typing?: boolean }[];
          return presences?.some((p) => p.typing);
        });
        setOtherTyping(anyoneTyping);
      })
      .subscribe();

    // Store ref so typing handler can access it
    presenceChannelRef.current = presenceChannel;

    return () => {
      supabase.removeChannel(presenceChannel);
      presenceChannelRef.current = null;
    };
  }, [threadId, currentUserId]);

  // Signal typing via Realtime presence (debounced — broadcasts every 3 seconds)
  const handleTextChange = useCallback((newText: string) => {
    setInputText(newText);
    if (!threadId || !newText.trim()) return;

    // Broadcast typing=true via presence (debounced to every 3s).
    // Defensive: track() may be missing on some Supabase mock channels;
    // skip silently rather than crashing the keystroke handler.
    if (!typingTimeoutRef.current && typeof presenceChannelRef.current?.track === 'function') {
      presenceChannelRef.current.track({ typing: true }).catch(() => {});
      typingTimeoutRef.current = setTimeout(() => {
        typingTimeoutRef.current = null;
      }, 3000);
    }

    // Clear typing after 3s of inactivity
    if (typingClearRef.current) clearTimeout(typingClearRef.current);
    typingClearRef.current = setTimeout(() => {
      if (typeof presenceChannelRef.current?.track === 'function') {
        presenceChannelRef.current.track({ typing: false }).catch(() => {});
      }
    }, 3000);
  }, [threadId]);

  // Send message with optimistic UI
  const handleSend = async () => {
    if (!inputText.trim() || !threadId || sending) return;

    const tempId = `temp-${Date.now()}`;
    const text = inputText.trim();
    setInputText('');
    setSending(true);

    // Clear typing indicator via presence (defensive — track may be missing
    // on Supabase mock channels; see makeChannel in src/lib/supabase.ts).
    if (typingClearRef.current) clearTimeout(typingClearRef.current);
    if (typeof presenceChannelRef.current?.track === 'function') {
      presenceChannelRef.current.track({ typing: false }).catch(() => {});
    }

    // Optimistic: add message with 'sending' status
    const optimisticMsg: LocalMessage = {
      id: tempId,
      threadId,
      authorUserId: currentUserId,
      text,
      createdAt: new Date().toISOString(),
      localStatus: 'sending',
    };
    setMessages((prev) => [...prev, optimisticMsg]);

    // Scroll to bottom
    setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);

    try {
      const sentMsg = await dataProvider.sendMessage(threadId, text);
      // Replace temp message with server response
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId
            ? { ...sentMsg, localStatus: 'sent' }
            : m
        )
      );
    } catch (err: unknown) {
      logger.error('[ThreadDetail] sendMessage error:', err);
      // Mark as failed
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId ? { ...m, localStatus: 'failed' } : m
        )
      );
      setFailedMessageIds((prev) => new Set(prev).add(tempId));
    } finally {
      setSending(false);
    }
  };

  const handleRetryMessage = async (tempId: string, text: string) => {
    // Remove from failed set and mark as sending again
    setFailedMessageIds((prev) => { const next = new Set(prev); next.delete(tempId); return next; });
    setMessages((prev) =>
      prev.map((m) =>
        m.id === tempId ? { ...m, localStatus: 'sending' } : m
      )
    );

    try {
      const sentMsg = await dataProvider.sendMessage(threadId!, text);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId ? { ...sentMsg, localStatus: 'sent' } : m
        )
      );
    } catch (err: unknown) {
      logger.error('[ThreadDetail] retryMessage error:', err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId ? { ...m, localStatus: 'failed' } : m
        )
      );
      setFailedMessageIds((prev) => new Set(prev).add(tempId));
    }
  };

  const handleScroll = useCallback((e: { nativeEvent: { contentOffset: { y: number }; layoutMeasurement: { height: number }; contentSize: { height: number } } }) => {
    const { contentOffset, layoutMeasurement, contentSize } = e.nativeEvent;
    const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
    isNearBottomRef.current = distanceFromBottom <= 150;
  }, []);

  const handleContentSizeChange = useCallback(() => {
    if (isNearBottomRef.current) {
      flatListRef.current?.scrollToEnd({ animated: false });
    }
  }, []);

  const renderMessage = ({ item, index }: { item: LocalMessage; index: number }) => {
    const isMe = currentUserId ? item.authorUserId === currentUserId : false;
    const isSending = item.localStatus === 'sending';
    const isFailed = item.localStatus === 'failed';
    const previousMessage = index > 0 ? messages[index - 1] : null;
    const showSeparator = shouldShowDateSeparator(item.createdAt, previousMessage?.createdAt ?? null);

    // Avatar for other user (from threadInfo)
    const otherAvatar = threadInfo?.otherUserAvatarUrl;
    const otherAvatarColor = threadInfo?.otherUserAvatarColor ?? '#6b7280';
    const otherInitial = threadInfo?.otherUserName?.charAt(0).toUpperCase() ?? '?';

    return (
      <View>
        {showSeparator && (
          <View style={styles.dateSeparator}>
            <View style={[styles.dateSeparatorLine, { backgroundColor: colors.border }]} />
            <Text style={[styles.dateSeparatorText, { color: colors.muted }]}>
              {formatDateSeparator(item.createdAt)}
            </Text>
            <View style={[styles.dateSeparatorLine, { backgroundColor: colors.border }]} />
          </View>
        )}
        <View
          style={[styles.messageRow, isMe ? styles.messageRowRight : styles.messageRowLeft]}
          accessibilityLabel={`${isMe ? 'You' : (threadInfo?.otherUserName || 'User')}: ${item.text}${isSending ? ', sending' : ''}${isFailed ? ', failed to send' : ''}`}
        >
          {/* Avatar for their messages */}
          {!isMe && (
            <View style={[styles.avatar, { backgroundColor: otherAvatar ? 'transparent' : otherAvatarColor }]}>
              {otherAvatar ? (
                <Image source={{ uri: otherAvatar }} style={styles.avatarImage} accessibilityLabel={`${threadInfo?.otherUserName || 'User'} avatar`} />
              ) : (
                <Text style={[styles.avatarInitial, { color: colors.accentText }]}>{otherInitial}</Text>
              )}
            </View>
          )}
          <View
            style={[
              styles.messageBubble,
              isMe
                ? [styles.myMessage, { backgroundColor: colors.accent }]
                : [styles.theirMessage, { backgroundColor: colors.card }],
            ]}
          >
            <Text style={[styles.messageText, { color: isMe ? colors.accentText : colors.text }]}>
              {item.text}
            </Text>
            <View style={styles.messageFooter}>
              <Text style={[styles.messageTime, { color: isMe ? colors.accentText + 'B3' : colors.muted }]}>
                {formatTime(item.createdAt)}
              </Text>
              {isMe && item.localStatus === 'sent' && (
                <Ionicons
                  name={item.readAt ? 'checkmark-done' : 'checkmark'}
                  size={14}
                  color={item.readAt ? (isMe ? colors.accentText + 'E6' : colors.accent) : (isMe ? colors.accentText + '80' : colors.muted)}
                  style={{ marginLeft: 4 }}
                />
              )}
              {isSending && (
                <ActivityIndicator size="small" color={isMe ? colors.accentText : colors.muted} style={{ marginLeft: 4 }} />
              )}
              {isFailed && (
                <Ionicons name="alert-circle" size={14} color={colors.danger} style={{ marginLeft: 4 }} />
              )}
            </View>
          </View>
        </View>
        {isFailed && failedMessageIds.has(item.id) && (
          <AnimatedPressable
            onPress={() => handleRetryMessage(item.id, item.text)}
            style={styles.retryRow}
            accessibilityRole="button"
            accessibilityLabel="Tap to retry sending message"
          >
            <Text style={[styles.retryLabel, { color: colors.danger }]}>Failed to send</Text>
            <Ionicons name="refresh" size={12} color={colors.danger} style={{ marginLeft: 2 }} />
            <Text style={[styles.retryAction, { color: colors.danger }]}>Tap to retry</Text>
          </AnimatedPressable>
        )}
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right', 'bottom']}>
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable onPress={() => safeGoBack(router)} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Chat</Text>
          <View style={{ width: 32 }} />
        </View>
        <View style={styles.loadingContainer}>
          <SkeletonChat />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right', 'bottom']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable onPress={() => safeGoBack(router)} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]} numberOfLines={1}>
          {threadInfo?.otherUserName || 'Chat'}
        </Text>
        <View style={{ width: 32 }} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {/* Messages */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={renderMessage}
          contentContainerStyle={styles.messageList}
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
          onScroll={handleScroll}
          scrollEventThrottle={100}
          onContentSizeChange={handleContentSizeChange}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="chatbubble-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyText, { color: colors.muted }]}>No messages yet</Text>
              <Text style={[styles.emptySubtext, { color: colors.muted }]}>Send a message to start the conversation</Text>
            </View>
          }
        />

        {/* Typing Indicator */}
        {otherTyping && (
          <View style={[styles.typingBar, { backgroundColor: colors.card, borderTopColor: colors.border }]} accessibilityLiveRegion="polite">
            <Text style={[styles.typingText, { color: colors.muted }]}>
              {threadInfo?.otherUserName ?? 'User'} is typing...
            </Text>
          </View>
        )}

        {/* Composer */}
        <View style={[styles.composer, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          <TextInput
            value={inputText}
            onChangeText={handleTextChange}
            placeholder="Type a message..."
            placeholderTextColor={colors.muted}
            accessibilityLabel="Message input"
            accessibilityHint="Type a message and press send"
            style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            multiline
            maxLength={1000}
            returnKeyType="send"
          />
          <AnimatedPressable
            onPress={handleSend}
            disabled={!inputText.trim() || sending}
            style={[
              styles.sendBtn,
              { backgroundColor: inputText.trim() ? colors.accent : colors.border },
            ]}
            accessibilityRole="button"
            accessibilityLabel={sending ? 'Sending message' : 'Send message'}
          >
            {sending ? (
              <ActivityIndicator size="small" color={colors.accentText} />
            ) : (
              <Ionicons name="send" size={18} color={colors.accentText} />
            )}
          </AnimatedPressable>
        </View>
      </KeyboardAvoidingView>
      <QuickNavBar />
    </SafeAreaView>
  );
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  flex1: {
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
    fontWeight: fontWeight.semibold,
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 8,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  messageList: {
    padding: 16,
    flexGrow: 1,
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: 4,
  },
  messageRowLeft: {
    justifyContent: 'flex-start',
  },
  messageRowRight: {
    justifyContent: 'flex-end',
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  avatarImage: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  messageBubble: {
    maxWidth: '78%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.lg,
  },
  myMessage: {
    alignSelf: 'flex-end',
    borderBottomRightRadius: radius.xs,
  },
  theirMessage: {
    alignSelf: 'flex-start',
    borderBottomLeftRadius: radius.xs,
    borderWidth: 0,
  },
  messageText: {
    fontSize: text.lg,
    lineHeight: 20,
  },
  messageFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  messageTime: {
    fontSize: text.xs,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 60,
  },
  emptyText: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: text.md,
    marginTop: 4,
    textAlign: 'center',
  },
  typingBar: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  typingText: {
    fontSize: text.md,
    fontStyle: 'italic',
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: 10,
  },
  input: {
    flex: 1,
    minHeight: 36,
    maxHeight: 100,
    borderRadius: radius.lg,
    paddingHorizontal: 14,
    paddingVertical: 8,
    fontSize: text.lg,
    borderWidth: 0,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingRight: 8,
    marginTop: 2,
    marginBottom: 4,
  },
  retryLabel: {
    fontSize: text.sm,
    marginRight: 4,
  },
  retryAction: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
    marginLeft: 2,
  },
  dateSeparator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
  },
  dateSeparatorLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
  },
  dateSeparatorText: {
    fontSize: text.sm,
    fontWeight: fontWeight.medium,
  },
});

export default function ThreadDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Chat">
      <ThreadDetailScreen />
    </ScreenErrorBoundary>
  );
}
