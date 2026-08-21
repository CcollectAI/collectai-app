/**
 * ShareToChatSheet — send an item or a marketplace listing into a DM.
 *
 * One sheet for both, because the two cards share the problem: a member spots
 * something and wants a specific person to see it. The alternative already in
 * the app is the OS share sheet (`ItemQuickActionsRow`), which leaves Sparrow
 * entirely and drops whoever receives it onto a link with no context.
 *
 * Sends through `sendChatMessage` (EC2), NOT the equivalent Supabase RPC: the
 * RPC writes the row but bypasses `_notify_new_message`, so the recipient gets
 * a message with no push. See src/api/chatApi.ts.
 *
 * Threads come from `listInboxThreads`, which only returns ACCEPTED threads —
 * `v_chat_inbox_v1` has no pending rows. That is deliberate: DM requests exist
 * so a stranger cannot put content in your inbox, and a share sheet that could
 * would be a hole straight through that rule.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Image, Share, Linking, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BottomSheetModal } from '@/components/BottomSheetModal';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { dataProvider } from '@/data';
import { sendChatMessage } from '@/api/chatApi';
import type { DmThread } from '@/data/types';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import { logger } from '@/lib/logger';

export type SharePayload = {
  /** What the recipient will recognise it by. */
  title: string;
  /** Already formatted for display — this component never formats money. */
  priceLabel?: string | null;
  /** Route to deep-link to, e.g. `listing/abc123` or `item/abc123`. No scheme,
   *  no leading slash — this builds the `sparrow://` URL. */
  route: string;
  /**
   * The PUBLIC https url, when the thing being shared has one
   * (`publicListingUrl`, src/lib/ids.ts). Preferred over `route` in the
   * message body, and it is the only shape that survives leaving the app: a
   * `sparrow://` string is not tappable in WhatsApp or iMessage, and a
   * recipient without Sparrow installed has nowhere to land.
   *
   * Inside the app the same url is turned back into a route by
   * `inAppListingHref`, so a DM'd listing opens the listing screen rather than
   * a browser. Omit it for things with no public page — an item is private.
   */
  webUrl?: string | null;
  imageUrl?: string | null;
};

/** The message body. Kept here so both cards produce the same shape. */
function composeMessage(p: SharePayload): string {
  const price = p.priceLabel ? ` — ${p.priceLabel}` : '';
  // https when there is one. `sparrow://` only for things with no public page,
  // where the recipient is by definition already a member reading it in-app.
  const link = p.webUrl || `sparrow://${p.route}`;
  return `${p.title}${price}\n${link}`;
}

/**
 * Where "send it outside Sparrow" goes first.
 *
 * Not a preference and not a guess at what is installed: iOS `canOpenURL` on a
 * third-party scheme answers false unless the scheme is declared in
 * `LSApplicationQueriesSchemes`, which `app.json` does not carry — so probing
 * would hide WhatsApp from every European member, which is the opposite of
 * this function. Both routes are always offered; region only decides which one
 * is on the left.
 *
 * `settings.region` is the app's existing signal (src/lib/settings.tsx), the
 * same one that picks the default currency.
 */
function messengersFor(region: string): ('whatsapp' | 'sms')[] {
  return region === 'americas' ? ['sms', 'whatsapp'] : ['whatsapp', 'sms'];
}

/** iMessage is an iOS product name; on Android the same intent is the SMS app. */
const SMS_LABEL = Platform.OS === 'ios' ? 'iMessage' : 'Messages';

/**
 * `wa.me`, not `whatsapp://send`. The custom scheme throws when WhatsApp is
 * absent (and needs the Info.plist declaration above to be probed at all);
 * wa.me opens the app when it is installed and a web page when it is not.
 *
 * `sms:` takes its body after `&` on iOS and `?` on Android — the one platform
 * split here, and getting it wrong opens Messages with an empty draft.
 */
function messengerUrl(target: 'whatsapp' | 'sms', body: string): string {
  const encoded = encodeURIComponent(body);
  if (target === 'whatsapp') return `https://wa.me/?text=${encoded}`;
  return `sms:${Platform.OS === 'ios' ? '&' : '?'}body=${encoded}`;
}

type Props = {
  visible: boolean;
  onClose: () => void;
  payload: SharePayload | null;
};

export function ShareToChatSheet({ visible, onClose, payload }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [threads, setThreads] = useState<DmThread[] | null>(null);
  // Tri-state, not a bare list: "no chats yet" and "still loading" render
  // identically if you only track the array (docs/ui-playbook.md).
  const [state, setState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [sendingTo, setSendingTo] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);

  // Fetched when the sheet opens rather than on mount — most sessions never
  // share anything. `visible` and the retry nonce are the only deps; nothing
  // this effect writes is one of its own dependencies (npm run check:effects).
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setState('loading');
    dataProvider
      .listInboxThreads()
      .then((list) => {
        if (cancelled) return;
        setThreads(list ?? []);
        setState('ok');
      })
      .catch((e) => {
        // logger.error, not warn — warn is stripped in release, which is
        // exactly where an empty picker would be invisible.
        logger.error('[ShareToChatSheet] thread list failed:', e);
        if (!cancelled) setState('error');
      });
    return () => { cancelled = true; };
  }, [visible, retryNonce]);

  const send = useCallback(
    async (thread: DmThread) => {
      if (!payload) return;
      setSendingTo(thread.id);
      try {
        await sendChatMessage(thread.id, composeMessage(payload));
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
        showToast({ message: `Sent to ${thread.otherUserName}`, type: 'success' });
        onClose();
      } catch (e: unknown) {
        logger.error('[ShareToChatSheet] send failed:', e);
        showToast({
          message: (e as Error)?.message || "Couldn't send that",
          type: 'error',
        });
      } finally {
        setSendingTo(null);
      }
    },
    [payload, onClose, showToast, settings.hapticsEnabled],
  );

  const shareOutside = useCallback(async () => {
    if (!payload) return;
    try {
      await Share.share({ message: composeMessage(payload) });
      onClose();
    } catch (e) {
      logger.error('[ShareToChatSheet] os share failed:', e);
    }
  }, [payload, onClose]);

  const openMessenger = useCallback(
    async (target: 'whatsapp' | 'sms') => {
      if (!payload) return;
      try {
        await Linking.openURL(messengerUrl(target, composeMessage(payload)));
        onClose();
      } catch (e) {
        // A missing app, or a device with no SMS. Hand the member the OS sheet
        // rather than a dead button — the same reasoning as the empty-chats
        // branch above: never leave someone on a control that goes nowhere.
        logger.error(`[ShareToChatSheet] ${target} open failed:`, e);
        showToast({ message: `Couldn't open ${target === 'whatsapp' ? 'WhatsApp' : SMS_LABEL}`, type: 'error' });
        await shareOutside();
      }
    },
    [payload, onClose, showToast, shareOutside],
  );

  const empty = state === 'ok' && (threads?.length ?? 0) === 0;

  return (
    <BottomSheetModal
      visible={visible}
      onClose={onClose}
      title="Send to"
      colors={colors}
      maxHeight="70%"
    >
      <ScrollView contentContainerStyle={styles.sheet} keyboardShouldPersistTaps="handled">
        {payload ? (
          <View style={[styles.preview, { borderColor: colors.border }]}>
            {payload.imageUrl ? (
              <Image source={{ uri: payload.imageUrl }} style={styles.previewThumb} />
            ) : (
              <View style={[styles.previewThumb, { backgroundColor: colors.background }]}>
                <Ionicons name="cube-outline" size={18} color={colors.muted} />
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={[styles.previewTitle, { color: colors.text }]} numberOfLines={2}>
                {payload.title}
              </Text>
              {payload.priceLabel ? (
                <Text style={[styles.previewPrice, { color: colors.muted }]}>{payload.priceLabel}</Text>
              ) : null}
            </View>
          </View>
        ) : null}

        {state === 'loading' ? (
          <Text style={[styles.hint, { color: colors.muted }]}>Loading your chats…</Text>
        ) : state === 'error' ? (
          <View style={styles.errorRow}>
            <Text style={[styles.hint, { color: colors.muted }]}>Couldn&apos;t load your chats.</Text>
            <AnimatedPressable
              onPress={() => setRetryNonce((n) => n + 1)}
              accessibilityRole="button"
              accessibilityLabel="Retry loading chats"
            >
              <Text style={[styles.link, { color: colors.accent }]}>Try again</Text>
            </AnimatedPressable>
          </View>
        ) : empty ? (
          // No empty shelf. A member with no chats is told why, and handed the
          // route that does work, rather than shown a blank list.
          <Text style={[styles.hint, { color: colors.muted }]}>
            No chats yet. Message someone from their profile or a listing first,
            then you can send items straight to them.
          </Text>
        ) : (
          (threads ?? []).map((t) => {
            const busy = sendingTo === t.id;
            return (
              <AnimatedPressable
                key={t.id}
                onPress={() => send(t)}
                disabled={sendingTo !== null}
                style={[styles.row, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel={`Send to ${t.otherUserName}`}
              >
                {t.otherUserAvatarUrl ? (
                  <Image source={{ uri: t.otherUserAvatarUrl }} style={styles.avatar} />
                ) : (
                  <View style={[styles.avatar, { backgroundColor: colors.accent + '22', alignItems: 'center', justifyContent: 'center' }]}>
                    <Text style={[styles.avatarText, { color: colors.accent }]}>
                      {(t.otherUserName || '?').slice(0, 1).toUpperCase()}
                    </Text>
                  </View>
                )}
                <Text style={[styles.rowName, { color: colors.text }]} numberOfLines={1}>
                  {t.otherUserName}
                </Text>
                <Text style={[styles.rowAction, { color: busy ? colors.muted : colors.accent }]}>
                  {busy ? 'Sending…' : 'Send'}
                </Text>
              </AnimatedPressable>
            );
          })
        )}

        {/* Outside Sparrow. One row, ordered by region — WhatsApp leads in
            Europe, iMessage in the Americas — with the OS sheet as the third
            pill for everything else (Signal, Telegram, Mail, AirDrop).

            `nowrap` with `flex: 1` on each pill, per docs/ui-playbook.md: a
            wrapping action row strands the last button on its own line. */}
        <Text style={[styles.groupLabel, { color: colors.muted }]}>Outside Sparrow</Text>
        <View style={styles.outsideRow}>
          {messengersFor(settings.region).map((target) => (
            <AnimatedPressable
              key={target}
              onPress={() => openMessenger(target)}
              style={[styles.outside, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel={
                target === 'whatsapp' ? 'Share on WhatsApp' : `Share by ${SMS_LABEL}`
              }
            >
              <Ionicons
                name={target === 'whatsapp' ? 'logo-whatsapp' : 'chatbubble-outline'}
                size={16}
                color={colors.muted}
              />
              <Text style={[styles.outsideText, { color: colors.text }]} numberOfLines={1}>
                {target === 'whatsapp' ? 'WhatsApp' : SMS_LABEL}
              </Text>
            </AnimatedPressable>
          ))}
          <AnimatedPressable
            onPress={shareOutside}
            style={[styles.outside, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Share somewhere else"
          >
            <Ionicons name="ellipsis-horizontal" size={16} color={colors.muted} />
            <Text style={[styles.outsideText, { color: colors.text }]} numberOfLines={1}>
              More
            </Text>
          </AnimatedPressable>
        </View>
      </ScrollView>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  sheet: { padding: 16, paddingBottom: 32, gap: 10 },
  preview: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm, padding: 10,
  },
  previewThumb: { width: 44, height: 44, borderRadius: radius.xs, alignItems: 'center', justifyContent: 'center' },
  previewTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold, lineHeight: 19 },
  previewPrice: { fontSize: textToken.sm, marginTop: 2 },
  hint: { fontSize: textToken.md, lineHeight: 20 },
  link: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 11,
  },
  avatar: { width: 32, height: 32, borderRadius: 16 },
  avatarText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  rowName: { flex: 1, fontSize: textToken.md, fontWeight: fontWeight.semibold },
  rowAction: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  groupLabel: { fontSize: textToken.sm, lineHeight: 17, marginTop: 6 },
  outsideRow: { flexDirection: 'row', flexWrap: 'nowrap', gap: 8 },
  outside: {
    flex: 1, flexShrink: 1,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md,
    paddingVertical: 12, paddingHorizontal: 8,
  },
  outsideText: { fontSize: textToken.md, fontWeight: fontWeight.semibold, flexShrink: 1, textAlign: 'center' },
});
