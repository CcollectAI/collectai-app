import React, { useMemo, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
import {
  getCategoryRoomById,
  getMessagesForRoom,
  CategoryChatMessage,
} from '@/data/chat';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

const BG = '#0f172a';
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';
const PRIMARY = '#0ea5e9';

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
      style={{
        width: 26,
        height: 26,
        borderRadius: 13,
        backgroundColor: color,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 8,
      }}
    >
      <Text
        style={{
          fontSize: 11,
          fontWeight: '700',
          color: '#ffffff',
        }}
      >
        {initials}
      </Text>
    </View>
  );
};

const CategoryChatScreen: React.FC = () => {
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const router = useRouter();
  const { settings } = useSettings();

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
      <View
        style={{
          flex: 1,
          backgroundColor: BG,
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: 16,
        }}
      >
        <Text
          style={{
            fontSize: 16,
            fontWeight: '600',
            color: TEXT,
            marginBottom: 8,
          }}
        >
          Category chat not found
        </Text>
        <Text
          style={{
            fontSize: 13,
            color: MUTED,
            textAlign: 'center',
          }}
        >
          This category doesn&apos;t have a chat room yet.
        </Text>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.back();
          }}
          style={{
            marginTop: 16,
            paddingHorizontal: 16,
            paddingVertical: 10,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: BORDER,
          }}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: '500',
              color: TEXT,
            }}
          >
            Go back
          </Text>
        </AnimatedPressable>
      </View>
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
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: BG }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}
    >
      <View style={{ flex: 1 }}>
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{
            paddingTop: 48,
            paddingBottom: 80,
            paddingHorizontal: 16,
          }}
        >
          {/* Header */}
          <View
            style={{
              marginBottom: 12,
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.back();
                }}
                style={{
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderRadius: 999,
                  borderWidth: 1,
                  borderColor: BORDER,
                  marginRight: 8,
                }}
                accessibilityRole="button"
                accessibilityLabel="Go back"
              >
                <Text
                  style={{
                    fontSize: 11,
                    color: MUTED,
                  }}
                >
                  Back
                </Text>
              </AnimatedPressable>
              <View>
                <Text
                  style={{
                    fontSize: 16,
                    fontWeight: '700',
                    color: TEXT,
                  }}
                >
                  {room.title}
                </Text>
                <Text
                  style={{
                    marginTop: 2,
                    fontSize: 11,
                    color: MUTED,
                  }}
                  numberOfLines={1}
                >
                  Category: {category.name}
                </Text>
              </View>
            </View>
          </View>

          {/* Room description */}
          <View
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 10,
              marginBottom: 12,
            }}
          >
            <Text
              style={{
                fontSize: 12,
                color: MUTED,
              }}
            >
              {room.description}
            </Text>
          </View>

          {/* Messages */}
          {messages.length === 0 ? (
            <Text
              style={{
                fontSize: 12,
                color: MUTED,
              }}
            >
              No messages yet. Start the conversation for this category.
            </Text>
          ) : (
            messages.map((m) => {
              const author = getUserById(m.authorUserId);
              return (
                <View
                  key={m.id}
                  style={{
                    marginBottom: 10,
                    flexDirection: 'row',
                    alignItems: 'flex-start',
                  }}
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
                    style={{
                      flex: 1,
                      borderRadius: 12,
                      borderWidth: 1,
                      borderColor: BORDER,
                      backgroundColor: CARD,
                      padding: 8,
                    }}
                  >
                    <View
                      style={{
                        flexDirection: 'row',
                        justifyContent: 'space-between',
                        marginBottom: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 11,
                          fontWeight: '600',
                          color: TEXT,
                        }}
                        numberOfLines={1}
                      >
                        {author ? author.displayName : 'Unknown collector'}
                      </Text>
                      <Text
                        style={{
                          fontSize: 10,
                          color: MUTED,
                          marginLeft: 8,
                        }}
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
                    <Text
                      style={{
                        fontSize: 12,
                        color: TEXT,
                      }}
                    >
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
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            paddingHorizontal: 16,
            paddingVertical: 8,
            borderTopWidth: 1,
            borderTopColor: BORDER,
            backgroundColor: BG,
          }}
        >
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
            }}
          >
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Share a thought, tip, or question…"
              placeholderTextColor={MUTED}
              accessibilityLabel="Chat message"
              style={{
                flex: 1,
                borderRadius: 999,
                borderWidth: 1,
                borderColor: BORDER,
                backgroundColor: CARD,
                paddingHorizontal: 12,
                paddingVertical: 8,
                fontSize: 13,
                color: TEXT,
              }}
            />
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                handleSend();
              }}
              disabled={!draft.trim()}
              style={{
                marginLeft: 8,
                paddingHorizontal: 12,
                paddingVertical: 8,
                borderRadius: 999,
                backgroundColor: draft.trim() ? PRIMARY : BORDER,
                opacity: draft.trim() ? 1 : 0.6,
                flexDirection: 'row',
                alignItems: 'center',
              }}
              accessibilityRole="button"
              accessibilityLabel="Send message"
            >
              <Ionicons name="send-outline" size={16} color="#ffffff" />
            </AnimatedPressable>
          </View>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
};

export default CategoryChatScreen;
