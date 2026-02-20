import React, { useMemo, useState, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
import {
  getCategoryRoomById,
  getMessagesForRoom,
  CategoryChatMessage,
} from '@/data/chat';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

const AvatarSmall: React.FC<{ name: string; color: string }> = ({ name, color }) => {
  const initials =
    name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';
  return (
    <View
      style={[styles.avatarSmall, { backgroundColor: color }]}
    >
      <Text style={styles.avatarSmallText}>
        {initials}
      </Text>
    </View>
  );
};

const CategoryChatScreen: React.FC = () => {
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const scrollRef = useRef<ScrollView>(null);

  const category = useMemo(
    () => (categoryId ? getCategoryById(categoryId) : undefined),
    [categoryId],
  );
  const room = useMemo(
    () => getCategoryRoomById(categoryId ?? null),
    [categoryId],
  );
  const initialMessages = useMemo(
    () => (room ? getMessagesForRoom(room.id) : []),
    [room],
  );

  const [messages, setMessages] = useState<CategoryChatMessage[]>(initialMessages);
  const [draft, setDraft] = useState('');

  if (!category || !room) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.emptyContainer}>
          <Ionicons name="chatbubbles-outline" size={48} color={colors.muted} />
          <Text
            style={[styles.emptyTitle, { color: colors.text }]}
          >
            Category chat not found
          </Text>
          <Text
            style={[styles.emptySubtitle, { color: colors.muted }]}
          >
            This category doesn&apos;t have a chat room yet.
          </Text>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.back();
            }}
            style={[styles.emptyBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text
              style={[styles.emptyBtnText, { color: colors.text }]}
            >
              Go back
            </Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;

    // Mock "current user" as Aurora for now
    const newMessage: CategoryChatMessage = {
      id: `local-${Date.now()}`,
      roomId: room.id,
      authorUserId: 'collector-aurora',
      text,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setDraft('');
    logger.info('[CategoryChat] send message', newMessage);

    // Scroll to bottom after new message
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.back();
            }}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <View style={styles.headerCenter}>
            <Text style={[styles.headerTitle, { color: colors.text }]} numberOfLines={1}>
              {room.title}
            </Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]} numberOfLines={1}>
              {category.name}
            </Text>
          </View>
          <View style={{ width: 32 }} />
        </View>

        <View style={styles.flex1}>
          <ScrollView
            ref={scrollRef}
            style={styles.flex1}
            contentContainerStyle={styles.scrollContent}
          >
            {/* Room description */}
            <View
              style={[styles.descriptionCard, { borderColor: colors.border, backgroundColor: colors.card }]}
            >
              <Text style={[styles.descriptionText, { color: colors.muted }]}>
                {room.description}
              </Text>
            </View>

            {/* Messages */}
            {messages.length === 0 ? (
              <View style={styles.noMessagesContainer}>
                <Ionicons name="chatbubble-outline" size={32} color={colors.muted} />
                <Text style={[styles.noMessagesText, { color: colors.muted }]}>
                  No messages yet. Start the conversation!
                </Text>
              </View>
            ) : (
              messages.map((m) => {
                const author = getUserById(m.authorUserId);
                return (
                  <View
                    key={m.id}
                    style={styles.messageRow}
                  >
                    {author && (
                      <AnimatedPressable
                        onPress={() => {
                          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                          router.push(`/users/${encodeURIComponent(author.id)}`);
                        }}
                        accessibilityRole="button"
                        accessibilityLabel={`View ${author.displayName}'s profile`}
                      >
                        <AvatarSmall
                          name={author.displayName}
                          color={author.avatarColor}
                        />
                      </AnimatedPressable>
                    )}
                    <View
                      style={[styles.messageBubble, { borderColor: colors.border, backgroundColor: colors.card }]}
                    >
                      <View style={styles.messageHeader}>
                        <Text
                          style={[styles.messageAuthor, { color: colors.text }]}
                          numberOfLines={1}
                        >
                          {author ? author.displayName : 'Unknown collector'}
                        </Text>
                        <Text
                          style={[styles.messageTime, { color: colors.muted }]}
                          numberOfLines={1}
                        >
                          {new Date(m.createdAt).toLocaleString('en-GB', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </Text>
                      </View>
                      <Text style={[styles.messageText, { color: colors.text }]}>
                        {m.text}
                      </Text>
                    </View>
                  </View>
                );
              })
            )}
          </ScrollView>

          {/* Input row */}
          <View
            style={[styles.composer, { borderTopColor: colors.border, backgroundColor: colors.background }]}
          >
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Share a thought, tip, or question..."
              placeholderTextColor={colors.muted}
              accessibilityLabel="Chat message"
              maxLength={500}
              style={[
                styles.composerInput,
                { borderColor: colors.border, backgroundColor: colors.card, color: colors.text },
              ]}
            />
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                handleSend();
              }}
              disabled={!draft.trim()}
              style={[
                styles.sendBtn,
                {
                  backgroundColor: draft.trim() ? colors.accent : colors.border,
                  opacity: draft.trim() ? 1 : 0.6,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Send message"
            >
              <Ionicons name="send-outline" size={16} color="#ffffff" />
            </AnimatedPressable>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

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
  headerCenter: {
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 8,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '700',
  },
  headerSubtitle: {
    marginTop: 1,
    fontSize: 11,
  },
  scrollContent: {
    paddingTop: 12,
    paddingBottom: 16,
    paddingHorizontal: 16,
  },
  descriptionCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 10,
    marginBottom: 12,
  },
  descriptionText: {
    fontSize: 12,
  },
  noMessagesContainer: {
    alignItems: 'center',
    paddingTop: 40,
    gap: 8,
  },
  noMessagesText: {
    fontSize: 13,
    textAlign: 'center',
  },
  messageRow: {
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  messageBubble: {
    flex: 1,
    borderRadius: 12,
    borderWidth: 1,
    padding: 8,
  },
  messageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  messageAuthor: {
    fontSize: 11,
    fontWeight: '600',
  },
  messageTime: {
    fontSize: 10,
    marginLeft: 8,
  },
  messageText: {
    fontSize: 12,
  },
  avatarSmall: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  avatarSmallText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#ffffff',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
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
  emptyBtn: {
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  emptyBtnText: {
    fontSize: 14,
    fontWeight: '500',
  },
  composer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    alignItems: 'center',
  },
  composerInput: {
    flex: 1,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
  },
  sendBtn: {
    marginLeft: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    flexDirection: 'row',
    alignItems: 'center',
  },
});

export default CategoryChatScreen;
