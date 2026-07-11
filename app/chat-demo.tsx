/**
 * Chat Demo — a self-contained PLACEHOLDER conversation so the chat UI can be
 * tested before there are real collectors to message. Nothing here touches the
 * server or dataProvider: messages are local-only and reset on unmount. This is
 * a temporary testing aid (reachable from the empty Inbox) — remove once real
 * DM threads exist.
 */
import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  type ListRenderItemInfo,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text, fontWeight } from '@/theme/tokens';

type DemoMessage = { id: string; text: string; fromMe: boolean };

const SEED: DemoMessage[] = [
  { id: 'd1', text: 'Hey! Saw you collect MTG too 🎴', fromMe: false },
  { id: 'd2', text: 'Yeah! Mostly reserved-list stuff. You?', fromMe: true },
  { id: 'd3', text: 'Same — chasing a Bayou right now. This is a demo chat so you can test the UI.', fromMe: false },
];

function ChatDemoScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const [messages, setMessages] = useState<DemoMessage[]>(SEED);
  const [draft, setDraft] = useState('');
  const seq = useRef(0);
  const listRef = useRef<FlatList<DemoMessage>>(null);

  const send = useCallback(() => {
    const body = draft.trim();
    if (!body) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    seq.current += 1;
    setMessages((prev) => [...prev, { id: `local-${seq.current}`, text: body, fromMe: true }]);
    setDraft('');
  }, [draft]);

  const renderItem = useCallback(
    ({ item }: ListRenderItemInfo<DemoMessage>) => (
      <View style={[styles.bubbleRow, item.fromMe ? styles.bubbleRowMe : styles.bubbleRowThem]}>
        <View
          style={[
            styles.bubble,
            item.fromMe
              ? { backgroundColor: colors.accent }
              : { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 },
          ]}
        >
          <Text style={[styles.bubbleText, { color: item.fromMe ? '#fff' : colors.text }]}>{item.text}</Text>
        </View>
      </View>
    ),
    [colors],
  );

  return (
    <KeyboardAvoidingView
      style={[styles.safe, { backgroundColor: colors.background }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={insets.bottom}
    >
      <SafeAreaView style={styles.flex} edges={['top', 'left', 'right']}>
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <View style={styles.headerTitleBlock}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Test Collector</Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>Placeholder · not saved</Text>
          </View>
          <View style={{ width: 32 }} />
        </View>

        <View style={[styles.demoBanner, { backgroundColor: colors.accent + '15' }]}>
          <Ionicons name="flask-outline" size={14} color={colors.accent} style={{ marginRight: 6 }} />
          <Text style={[styles.demoBannerText, { color: colors.accent }]}>
            Demo conversation for testing — messages stay on this device.
          </Text>
        </View>

        <FlatList
          ref={listRef}
          style={styles.flex}
          data={messages}
          keyExtractor={(m) => m.id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        />
        <View style={[styles.inputBar, { backgroundColor: colors.card, borderTopColor: colors.border, paddingBottom: insets.bottom || 8 }]}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Message…"
            placeholderTextColor={colors.muted}
            style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.border }]}
            onSubmitEditing={send}
            returnKeyType="send"
            accessibilityLabel="Type a test message"
          />
          <AnimatedPressable
            onPress={send}
            disabled={!draft.trim()}
            style={[styles.sendBtn, { backgroundColor: draft.trim() ? colors.accent : colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Send test message"
          >
            <Ionicons name="arrow-up" size={20} color="#fff" />
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: { padding: 4 },
  headerTitleBlock: { alignItems: 'center' },
  headerTitle: { fontSize: text.lg, fontWeight: fontWeight.bold },
  headerSub: { fontSize: text.xs, marginTop: 1 },
  demoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  demoBannerText: { fontSize: text.sm, flex: 1 },
  listContent: { padding: 12, gap: 8 },
  bubbleRow: { flexDirection: 'row' },
  bubbleRowMe: { justifyContent: 'flex-end' },
  bubbleRowThem: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '78%',
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: radius.md,
  },
  bubbleText: { fontSize: text.md, lineHeight: 20 },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === 'ios' ? 10 : 6,
    fontSize: text.md,
    maxHeight: 100,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default function ChatDemoScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Chat Demo">
      <ChatDemoScreen />
    </ScreenErrorBoundary>
  );
}
