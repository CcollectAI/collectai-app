/**
 * PaymentHandlesSection — where a seller says how buyers can pay them.
 *
 * This is the PRODUCER for the settle-up prefill. `/p2p/payment-rails` returns
 * `pay_url` per rail with the agreed amount already in it, built from the handle
 * stored here. Without this screen the consumer exists and nothing ever feeds
 * it, which is the half-built shape this codebase keeps writing down.
 *
 * What a handle is and is not
 * ---------------------------
 * It is the PUBLIC identifier a stranger can already pay — `paypal.me/merle`.
 * Not an account, not a credential, not a token. Sparrow still never touches
 * money, never learns whether payment happened, and never writes a "paid" flag
 * (docs/P2P_MARKETPLACE_SPEC.md §5a).
 *
 * Who can see it
 * --------------
 * `user_payment_handles` is owner-only under RLS. The one path that reads
 * someone else's handle is the server building a link for the BUYER of an
 * accepted trade — and it returns the link, never the handle. So a member's
 * handle reaches exactly the person who already agreed to pay them.
 *
 * Only rails with a `handle_label` appear. A rail with no public link format
 * (SEPA, Tikkie, Zelle) has nothing to collect, and asking for one would imply
 * a prefill that cannot happen.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, StyleSheet, ActivityIndicator } from 'react-native';

import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { collectorsApi } from '@/api/collectorsApi';
import type { P2PPaymentRail } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import { logger } from '@/lib/logger';

export function PaymentHandlesSection() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [rails, setRails] = useState<P2PPaymentRail[] | null>(null);
  const [handles, setHandles] = useState<Record<string, string>>({});
  const [state, setState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    Promise.all([
      collectorsApi.p2pListPaymentRails(),
      collectorsApi.p2pListPaymentHandles(),
    ])
      .then(([railsRes, handleRows]) => {
        if (cancelled) return;
        setRails(railsRes?.rails ?? []);
        const map: Record<string, string> = {};
        for (const h of handleRows ?? []) map[h.rail_key] = h.handle;
        setHandles(map);
        setState('ok');
      })
      .catch((e) => {
        // logger.error, not warn — warn is stripped in release builds, and a
        // silently empty settings section is invisible there.
        logger.error('[paymentHandles] load failed:', e);
        if (!cancelled) setState('error');
      });
    return () => { cancelled = true; };
  }, [retryNonce]);

  // Only rails that HAVE a public identifier to collect.
  const collectable = useMemo(
    () => (rails ?? []).filter((r) => !!r.handle_label),
    [rails],
  );

  const save = useCallback(
    async (railKey: string) => {
      setSavingKey(railKey);
      try {
        const rows = await collectorsApi.p2pSetPaymentHandle(railKey, handles[railKey] ?? '');
        const map: Record<string, string> = {};
        for (const h of rows ?? []) map[h.rail_key] = h.handle;
        setHandles(map);
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
        showToast({ message: 'Saved', type: 'success' });
      } catch (e: unknown) {
        // Surface the server's message: a rejected handle comes back with the
        // reason ("characters we cannot put in a link"), which is actionable —
        // a generic failure toast is not.
        logger.error('[paymentHandles] save failed:', e);
        showToast({ message: (e as Error)?.message || "Couldn't save that", type: 'error' });
      } finally {
        setSavingKey(null);
      }
    },
    [handles, showToast, settings.hapticsEnabled],
  );

  if (state === 'loading') {
    return (
      <View style={styles.section}>
        <Text style={[styles.heading, { color: colors.text }]}>Getting paid</Text>
        <ActivityIndicator color={colors.muted} style={{ marginTop: 12 }} />
      </View>
    );
  }

  if (state === 'error') {
    return (
      <View style={styles.section}>
        <Text style={[styles.heading, { color: colors.text }]}>Getting paid</Text>
        <View style={styles.errorRow}>
          <Text style={[styles.blurb, { color: colors.muted }]}>Couldn&apos;t load this.</Text>
          <AnimatedPressable
            onPress={() => setRetryNonce((n) => n + 1)}
            accessibilityRole="button"
            accessibilityLabel="Try again"
          >
            <Text style={[styles.link, { color: colors.accent }]}>Try again</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  if (collectable.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.heading, { color: colors.text }]}>Getting paid</Text>
      <Text style={[styles.blurb, { color: colors.muted }]}>
        Add the handle buyers can pay you on and Sparrow will open their app with
        the agreed amount already filled in. Only the buyer of a trade you have
        accepted ever sees it. Sparrow never handles the money.
      </Text>

      {collectable.map((r) => {
        const busy = savingKey === r.key;
        return (
          <View key={r.key} style={styles.row}>
            <Text style={[styles.railLabel, { color: colors.text }]}>{r.label}</Text>
            <View style={styles.inputRow}>
              <TextInput
                value={handles[r.key] ?? ''}
                onChangeText={(v) => setHandles((prev) => ({ ...prev, [r.key]: v }))}
                placeholder={r.handle_label ?? ''}
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                autoCorrect={false}
                maxLength={64}
                style={[
                  styles.input,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.card },
                ]}
                accessibilityLabel={`${r.label} ${r.handle_label ?? 'handle'}`}
              />
              <AnimatedPressable
                onPress={() => save(r.key)}
                disabled={busy}
                style={[styles.saveBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel={`Save your ${r.label} handle`}
              >
                <Text style={[styles.saveBtnText, { color: colors.accentText }]}>
                  {busy ? '…' : 'Save'}
                </Text>
              </AnimatedPressable>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: 16, paddingTop: 20, paddingBottom: 4 },
  heading: { fontSize: textToken.lg, fontWeight: fontWeight.bold },
  blurb: { fontSize: textToken.md, lineHeight: 20, marginTop: 6 },
  link: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8, flexWrap: 'wrap' },
  row: { marginTop: 14 },
  railLabel: { fontSize: textToken.sm, fontWeight: fontWeight.bold, marginBottom: 6 },
  inputRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  input: {
    flex: 1,
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontSize: textToken.md,
  },
  // paddingHorizontal is NOT optional on a content-sized button — see the
  // listing screen's primaryBtn, where omitting it put the label flush against
  // the fill.
  saveBtn: {
    paddingHorizontal: 18,
    paddingVertical: 11,
    borderRadius: radius.md,
  },
  saveBtnText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
});
