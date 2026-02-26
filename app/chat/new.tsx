import React, { useEffect, useMemo, useState } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { View, Text, TextInput, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getUserById } from '@/data/users';
import { EVENTS } from '@/data/events';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { EmptyState } from '@/components/EmptyState';
import logger from '@/utils/logger';

type DmStatusState = 'loading' | 'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined' | 'blocked';

const NewChatScreen: React.FC = () => {
  const { toUserId, contextEventId } = useLocalSearchParams<{
    toUserId?: string;
    contextEventId?: string;
  }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { showToast } = useToast();

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
  const [sending, setSending] = useState(false);
  const [dmStatus, setDmStatus] = useState<DmStatusState>('loading');

  // Check DM status and block state on mount
  useEffect(() => {
    if (!toUserId) return;

    const checkStatus = async () => {
      try {
        const [blocked, status] = await Promise.all([
          dataProvider.isBlocked(toUserId),
          dataProvider.getDmStatus(toUserId),
        ]);

        if (blocked) {
          setDmStatus('blocked');
        } else {
          setDmStatus(status);
        }
      } catch (err) {
        logger.warn('[Chat/new] status check error:', err);
        setDmStatus('none');
      }
    };

    checkStatus();
  }, [toUserId]);

  // Redirect to existing thread if already accepted
  useEffect(() => {
    if (dmStatus === 'accepted' && toUserId) {
      router.replace(`/inbox`);
    }
  }, [dmStatus, toUserId, router]);

  const handleSend = async () => {
    if (!toUserId || !message.trim() || sending) return;

    setSending(true);
    try {
      await dataProvider.requestDm(toUserId, message.trim());
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      setSent(true);
      setTimeout(() => {
        router.back();
      }, 800);
    } catch (err: unknown) {
      logger.error('[Chat/new] requestDm error:', err);
      showToast({ message: err instanceof Error ? err.message : 'Failed to send. Please try again.', type: 'error' });
    } finally {
      setSending(false);
    }
  };

  if (!toUser) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <EmptyState
          icon="person-outline"
          title="Collector not found"
          subtitle="This chat can't be started because the collector profile is missing."
          colors={colors}
          action={
            <AnimatedPressable
              onPress={() => router.back()}
              style={[styles.emptyBtn, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={[styles.emptyBtnText, { color: colors.text }]}>Go back</Text>
            </AnimatedPressable>
          }
        />
      </SafeAreaView>
    );
  }

  // Status-based UI states
  if (dmStatus === 'loading') {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  if (dmStatus === 'blocked') {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <EmptyState
          icon="ban-outline"
          title="Can't message this user"
          subtitle="You can't send a message to this collector."
          colors={colors}
          action={
            <AnimatedPressable
              onPress={() => router.back()}
              style={[styles.emptyBtn, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={[styles.emptyBtnText, { color: colors.text }]}>Go back</Text>
            </AnimatedPressable>
          }
        />
      </SafeAreaView>
    );
  }

  if (dmStatus === 'pending_outgoing') {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <EmptyState
          icon="hourglass-outline"
          title="Request already sent"
          subtitle={`You've already sent a connection request to ${toUser.displayName}. They haven't responded yet.`}
          iconColor={colors.accent}
          colors={colors}
          action={
            <AnimatedPressable
              onPress={() => router.back()}
              style={[styles.emptyBtn, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={[styles.emptyBtnText, { color: colors.text }]}>Go back</Text>
            </AnimatedPressable>
          }
        />
      </SafeAreaView>
    );
  }

  if (dmStatus === 'pending_incoming') {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <EmptyState
          icon="mail-unread-outline"
          title={`You have a request from ${toUser.displayName}`}
          subtitle="Check your inbox to accept or decline their connection request."
          iconColor={colors.accent}
          colors={colors}
          action={
            <AnimatedPressable
              onPress={() => router.push('/inbox')}
              style={[styles.emptyBtn, { borderColor: colors.accent, backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Go to inbox"
            >
              <Text style={[styles.emptyBtnText, { color: '#ffffff' }]}>Go to Inbox</Text>
            </AnimatedPressable>
          }
        />
      </SafeAreaView>
    );
  }

  const initials = toUser.displayName
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const canSend = message.trim().length > 0 && !sent && !sending;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
      >
        <View style={styles.content}>
          {/* Header */}
          <View style={styles.header}>
            <AnimatedPressable onPress={() => router.back()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </AnimatedPressable>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Request to Connect</Text>
            <View style={{ width: 32 }} />
          </View>

          {/* Recipient card */}
          <View style={[styles.recipientCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={[styles.avatar, { backgroundColor: toUser.avatarColor }]}>
              <Text style={styles.avatarText}>{initials}</Text>
            </View>
            <View style={styles.recipientInfo}>
              <Text style={[styles.recipientName, { color: colors.text }]}>
                {toUser.displayName}
              </Text>
              <Text style={[styles.recipientHandle, { color: colors.muted }]}>
                @{toUser.handle}
              </Text>
              {contextEvent && (
                <View style={styles.contextRow}>
                  <Ionicons name="calendar-outline" size={12} color={colors.accent} />
                  <Text style={[styles.contextText, { color: colors.accent }]} numberOfLines={1}>
                    {contextEvent.title}
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Message input */}
          <View style={[styles.messageCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.messageLabelRow}>
              <Ionicons name="chatbubble-outline" size={14} color={colors.muted} />
              <Text style={[styles.messageLabel, { color: colors.muted }]}>Your message</Text>
            </View>
            <TextInput
              multiline
              value={message}
              onChangeText={setMessage}
              placeholder={
                contextEvent
                  ? 'Write a friendly message about this event\u2026'
                  : 'Write a friendly message\u2026'
              }
              placeholderTextColor={colors.muted}
              accessibilityLabel="Connection message"
              maxLength={1000}
              editable={!sending && !sent}
              style={[styles.messageInput, { color: colors.text }]}
            />
          </View>

          {/* Send button */}
          <AnimatedPressable
            disabled={!canSend}
            onPress={handleSend}
            style={[
              styles.sendBtn,
              {
                backgroundColor: canSend ? colors.accent : colors.border,
                opacity: canSend ? 1 : 0.6,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={sent ? 'Request sent' : 'Send connection request'}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Ionicons
                name={sent ? 'checkmark-circle' : 'send'}
                size={18}
                color="#ffffff"
              />
            )}
            <Text style={styles.sendBtnText}>
              {sent ? 'Request sent!' : sending ? 'Sending...' : 'Send connection request'}
            </Text>
          </AnimatedPressable>

          {/* Info text */}
          <Text style={[styles.infoText, { color: colors.muted }]}>
            They'll receive a notification and can choose to accept or decline your request.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
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
  recipientCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    marginTop: 8,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#ffffff',
  },
  recipientInfo: {
    flex: 1,
    marginLeft: 12,
  },
  recipientName: {
    fontSize: 16,
    fontWeight: '600',
  },
  recipientHandle: {
    fontSize: 13,
    marginTop: 2,
  },
  contextRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 4,
  },
  contextText: {
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
  },
  messageCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginTop: 16,
  },
  messageLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  messageLabel: {
    fontSize: 13,
    fontWeight: '600',
  },
  messageInput: {
    minHeight: 120,
    fontSize: 15,
    lineHeight: 22,
    textAlignVertical: 'top',
  },
  sendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    marginTop: 20,
    gap: 8,
  },
  sendBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#ffffff',
  },
  infoText: {
    fontSize: 12,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 18,
  },
});

export default function NewChatScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="New Chat">
      <NewChatScreen />
    </ScreenErrorBoundary>
  );
}
