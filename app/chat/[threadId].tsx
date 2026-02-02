/**
 * Thread Detail Screen — View messages + send new messages.
 * Route: /chat/[threadId]
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type DmMessage, type DmThread, type PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

// Message with local status for optimistic UI
type LocalMessage = DmMessage & {
  localStatus?: 'sending' | 'sent' | 'failed';
};

export default function ThreadDetailScreen() {
  const router = useRouter();
  const { threadId } = useLocalSearchParams<{ threadId: string }>();
  const { colors } = useAppTheme();

  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [threadInfo, setThreadInfo] = useState<DmThread | null>(null);
  const [currentUser, setCurrentUser] = useState<PublicUserProfile | null>(null);

  const flatListRef = useRef<FlatList>(null);

  // Current user ID (fallback for rendering before profile loads)
  const currentUserId = currentUser?.id ?? 'collector-aurora';

  // Load messages
  const loadMessages = useCallback(async () => {
    if (!threadId) return;
    try {
      const msgs = await dataProvider.getThreadMessages(threadId);
      setMessages(msgs.map((m) => ({ ...m, localStatus: 'sent' })));
    } catch (err) {
      console.warn('[ThreadDetail] loadMessages error:', err);
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
      console.warn('[ThreadDetail] loadThreadInfo error:', err);
    }
  }, [threadId]);

  // Load current user profile
  const loadCurrentUser = useCallback(async () => {
    try {
      const profile = await dataProvider.getMyProfile();
      if (profile) setCurrentUser(profile);
    } catch (err) {
      console.warn('[ThreadDetail] loadCurrentUser error:', err);
    }
  }, []);

  useEffect(() => {
    loadMessages();
    loadThreadInfo();
    loadCurrentUser();
    // Mark thread as read (best-effort)
    if (threadId) {
      dataProvider.markThreadRead(threadId).catch(() => {});
    }
  }, [loadMessages, loadThreadInfo, loadCurrentUser, threadId]);

  // Send message with optimistic UI
  const handleSend = async () => {
    if (!inputText.trim() || !threadId || sending) return;

    const tempId = `temp-${Date.now()}`;
    const text = inputText.trim();
    setInputText('');
    setSending(true);

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
    } catch (err: any) {
      console.warn('[ThreadDetail] sendMessage error:', err);
      // Mark as failed
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId ? { ...m, localStatus: 'failed' } : m
        )
      );
    } finally {
      setSending(false);
    }
  };

  const renderMessage = ({ item }: { item: LocalMessage }) => {
    const isMe = item.authorUserId === currentUserId;
    const isSending = item.localStatus === 'sending';
    const isFailed = item.localStatus === 'failed';

    // Avatar for other user (from threadInfo)
    const otherAvatar = threadInfo?.otherUserAvatarUrl;
    const otherAvatarColor = threadInfo?.otherUserAvatarColor ?? '#6b7280';
    const otherInitial = threadInfo?.otherUserName?.charAt(0).toUpperCase() ?? '?';

    return (
      <View style={[styles.messageRow, isMe ? styles.messageRowRight : styles.messageRowLeft]}>
        {/* Avatar for their messages */}
        {!isMe && (
          <View style={[styles.avatar, { backgroundColor: otherAvatar ? 'transparent' : otherAvatarColor }]}>
            {otherAvatar ? (
              <Image source={{ uri: otherAvatar }} style={styles.avatarImage} />
            ) : (
              <Text style={styles.avatarInitial}>{otherInitial}</Text>
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
          <Text style={[styles.messageText, { color: isMe ? '#fff' : colors.text }]}>
            {item.text}
          </Text>
          <View style={styles.messageFooter}>
            <Text style={[styles.messageTime, { color: isMe ? 'rgba(255,255,255,0.7)' : colors.muted }]}>
              {formatTime(item.createdAt)}
            </Text>
            {isSending && (
              <ActivityIndicator size="small" color={isMe ? '#fff' : colors.muted} style={{ marginLeft: 4 }} />
            )}
            {isFailed && (
              <Ionicons name="alert-circle" size={14} color="#ef4444" style={{ marginLeft: 4 }} />
            )}
          </View>
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right', 'bottom']}>
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Chat</Text>
          <View style={{ width: 32 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right', 'bottom']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable onPress={() => router.back()} style={styles.backBtn}>
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
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="chatbubble-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyText, { color: colors.muted }]}>No messages yet</Text>
              <Text style={[styles.emptySubtext, { color: colors.muted }]}>Send a message to start the conversation</Text>
            </View>
          }
        />

        {/* Composer */}
        <View style={[styles.composer, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          <TextInput
            value={inputText}
            onChangeText={setInputText}
            placeholder="Type a message..."
            placeholderTextColor={colors.muted}
            style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
            multiline
            maxLength={1000}
          />
          <AnimatedPressable
            onPress={handleSend}
            disabled={!inputText.trim() || sending}
            style={[
              styles.sendBtn,
              { backgroundColor: inputText.trim() ? colors.accent : colors.border },
            ]}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Ionicons name="send" size={18} color="#fff" />
            )}
          </AnimatedPressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

// Static styles only — no theme tokens
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
    fontSize: 17,
    fontWeight: '600',
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
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  messageBubble: {
    maxWidth: '78%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 18,
  },
  myMessage: {
    alignSelf: 'flex-end',
    borderBottomRightRadius: 6,
  },
  theirMessage: {
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 6,
    borderWidth: 0,
  },
  messageText: {
    fontSize: 15,
    lineHeight: 20,
  },
  messageFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  messageTime: {
    fontSize: 11,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 60,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    marginTop: 4,
    textAlign: 'center',
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
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 8,
    fontSize: 16,
    borderWidth: 0,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
