import React, { useMemo, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getUserById } from '@/data/users';
import { EVENTS } from '@/data/events';

const BG = '#0f172a';
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';
const PRIMARY = '#0ea5e9';

const NewChatScreen: React.FC = () => {
  const { toUserId, contextEventId } = useLocalSearchParams<{
    toUserId?: string;
    contextEventId?: string;
  }>();
  const router = useRouter();

  const toUser = useMemo(() => getUserById(toUserId ?? null), [toUserId]);
  const contextEvent = useMemo(
    () => EVENTS.find((e) => e.id === contextEventId),
    [contextEventId],
  );

  const [message, setMessage] = useState(
    contextEvent
      ? `Hey, I saw you on the attendee list for "${contextEvent.title}". Want to connect?`
      : '',
  );
  const [sent, setSent] = useState(false);

  const handleSend = () => {
    console.log('[Chat] send connection message', {
      toUserId,
      contextEventId,
      message,
    });
    setSent(true);
    setTimeout(() => {
      router.back();
    }, 800);
  };

  if (!toUser) {
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
          Collector not found
        </Text>
        <Text
          style={{
            fontSize: 13,
            color: MUTED,
            textAlign: 'center',
          }}
        >
          This chat can&apos;t be started because the collector profile is
          missing.
        </Text>
        <TouchableOpacity
          onPress={() => router.back()}
          style={{
            marginTop: 16,
            paddingHorizontal: 16,
            paddingVertical: 10,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: BORDER,
          }}
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
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: BG }}
      contentContainerStyle={{
        paddingTop: 48,
        paddingBottom: 32,
        paddingHorizontal: 16,
      }}
    >
      {/* Header */}
      <View
        style={{
          marginBottom: 16,
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <TouchableOpacity
            onPress={() => router.back()}
            style={{
              paddingHorizontal: 10,
              paddingVertical: 6,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: BORDER,
              marginRight: 8,
            }}
          >
            <Text
              style={{
                fontSize: 11,
                color: MUTED,
              }}
            >
              Back
            </Text>
          </TouchableOpacity>
          <Text
            style={{
              fontSize: 18,
              fontWeight: '700',
              color: TEXT,
            }}
          >
            Ask to connect
          </Text>
        </View>
      </View>

      {/* Target info */}
      <View
        style={{
          borderRadius: 16,
          borderWidth: 1,
          borderColor: BORDER,
          backgroundColor: CARD,
          padding: 12,
          marginBottom: 12,
          flexDirection: 'row',
          alignItems: 'center',
        }}
      >
        <View
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            backgroundColor: toUser.avatarColor,
            alignItems: 'center',
            justifyContent: 'center',
            marginRight: 8,
          }}
        >
          <Text
            style={{
              fontSize: 14,
              fontWeight: '700',
              color: '#ffffff',
            }}
          >
            {toUser.displayName
              .split(' ')
              .map((p) => p[0])
              .join('')
              .slice(0, 2)
              .toUpperCase()}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontSize: 14,
              fontWeight: '600',
              color: TEXT,
            }}
          >
            {toUser.displayName}
          </Text>
          <Text
            style={{
              fontSize: 11,
              color: MUTED,
            }}
          >
            @{toUser.handle}
          </Text>
          {contextEvent && (
            <Text
              style={{
                marginTop: 2,
                fontSize: 11,
                color: MUTED,
              }}
              numberOfLines={1}
            >
              About: {contextEvent.title}
            </Text>
          )}
        </View>
      </View>

      {/* Message box */}
      <View
        style={{
          borderRadius: 16,
          borderWidth: 1,
          borderColor: BORDER,
          backgroundColor: CARD,
          padding: 12,
          marginBottom: 12,
        }}
      >
        <Text
          style={{
            fontSize: 13,
            fontWeight: '600',
            color: TEXT,
            marginBottom: 6,
          }}
        >
          Message
        </Text>
        <TextInput
          multiline
          value={message}
          onChangeText={setMessage}
          placeholder={
            contextEvent
              ? 'Write a short message about this event…'
              : 'Write a short message…'
          }
          placeholderTextColor={MUTED}
          style={{
            minHeight: 100,
            fontSize: 13,
            color: TEXT,
            textAlignVertical: 'top',
          }}
        />
      </View>

      {/* Send button */}
      <TouchableOpacity
        disabled={!message.trim()}
        onPress={handleSend}
        style={{
          alignSelf: 'flex-start',
          paddingHorizontal: 16,
          paddingVertical: 10,
          borderRadius: 999,
          backgroundColor: message.trim() ? PRIMARY : BORDER,
          flexDirection: 'row',
          alignItems: 'center',
          opacity: message.trim() ? 1 : 0.6,
        }}
      >
        <Ionicons
          name={sent ? 'checkmark-circle-outline' : 'send-outline'}
          size={16}
          color="#ffffff"
          style={{ marginRight: 6 }}
        />
        <Text
          style={{
            fontSize: 13,
            fontWeight: '600',
            color: '#ffffff',
          }}
        >
          {sent ? 'Request sent (mock)' : 'Send request'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

export default NewChatScreen;
