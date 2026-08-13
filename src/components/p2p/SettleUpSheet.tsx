/**
 * SettleUpSheet — how the two members finish a trade off-platform.
 *
 * Buyer side: the payment rails available in their region.
 * Seller side: where to book the parcel.
 *
 * **Sparrow is a directory in both halves and a participant in neither.** It
 * links out; the members transact under their own accounts with their own
 * providers. docs/P2P_MARKETPLACE_SPEC.md §5a is the governing text:
 *
 *  - A hyperlink is not payment initiation under PSD2 Art. 4(15) — the user's
 *    own PSP initiates the order. Holding funds, even momentarily, is the line,
 *    and there is no de-minimis.
 *  - Rails may be compared NEUTRALLY on reversibility. Saying "we recommend X"
 *    is a representation about a payment provider. That is why the server
 *    returns them alphabetically and this component renders them in the order
 *    it is given — do not sort, pin or highlight one here.
 *  - The seller books carriage in their OWN name. Generating labels under a
 *    Sparrow carrier account would make us the contracting party; arranging
 *    insurance would be insurance distribution under IDD. Both are links here.
 *  - Nothing in this sheet writes to the trade. Completion stays the two-sided
 *    confirm, which only a human sets.
 *
 * No amount prefill: `paypal.me/<handle>/<amount>` needs the SELLER's handle and
 * no column holds one (verified against the live schema 2026-08-14). The amount
 * is rendered `selectable` instead — the same choice the tracking code makes,
 * because expo-clipboard is not installed and a guarded require of a missing
 * package is a silent no-op on both platforms.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BottomSheetModal } from '@/components/BottomSheetModal';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { collectorsApi } from '@/api/collectorsApi';
import { useSettings } from '@/lib/settings';
import type { P2PCarrier, P2PPaymentRail } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import { logger } from '@/lib/logger';

/** Same shape `OfferAmountSheet` takes — an index signature of `unknown`, not
 *  `string`, because the theme's `brand` value is a nested object and a
 *  `Record<string, string>` rejects the whole palette. */
type SheetColors = {
  text: string;
  muted: string;
  card: string;
  border: string;
  accent: string;
  accentText: string;
  background: string;
  [key: string]: unknown;
};

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Buyers get rails, sellers get carriers. A member is usually both across
   *  trades, but never on the same one. */
  mode: 'pay' | 'ship';
  /** Already formatted — this component never formats money. */
  amountLabel: string;
  colors: SheetColors;
};

function openUrl(url: string) {
  // Scheme-checked before opening: these come from the server, but an
  // open-redirect through Linking is cheap to prevent and expensive to miss.
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      Linking.openURL(url).catch((e) => logger.error('[settleUp] open failed:', e));
    }
  } catch (e) {
    logger.error('[settleUp] bad url:', e);
  }
}

export function SettleUpSheet({ visible, onClose, mode, amountLabel, colors }: Props) {
  // The payment side resolves region SERVER-side from user_settings; the
  // carrier list is one flat table, so the filtering happens here. Same region
  // value either way.
  const { settings } = useSettings();
  const [rails, setRails] = useState<P2PPaymentRail[] | null>(null);
  const [carriers, setCarriers] = useState<P2PCarrier[] | null>(null);
  const [disclaimer, setDisclaimer] = useState<string>('');
  // Tri-state: "none available" and "still loading" render identically if you
  // only track the array (docs/ui-playbook.md).
  const [state, setState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setState('loading');
    const load = mode === 'pay'
      ? collectorsApi.p2pListPaymentRails().then((res) => {
          if (cancelled) return;
          setRails(res?.rails ?? []);
          setDisclaimer(res?.disclaimer ?? '');
        })
      : collectorsApi.p2pListCarriers().then((list) => {
          if (cancelled) return;
          // Two filters, and the region one is easy to forget: the server sends
          // every carrier it knows, so without it a seller in the Netherlands
          // is offered Australia Post. `regions` absent (an older server that
          // predates the booking table) means we cannot tell — show it rather
          // than hide a carrier that may be right.
          setCarriers(
            (list ?? []).filter(
              (c) =>
                !!c.book_url &&
                (!c.regions?.length || c.regions.includes(settings.region)),
            ),
          );
        });
    load
      .then(() => { if (!cancelled) setState('ok'); })
      .catch((e) => {
        // logger.error, not warn — warn is stripped in release, which is
        // exactly where an empty sheet would be invisible.
        logger.error('[settleUp] load failed:', e);
        if (!cancelled) setState('error');
      });
    return () => { cancelled = true; };
  }, [visible, mode, retryNonce, settings.region]);

  const reversibilityLabel = useCallback((r: P2PPaymentRail): string => {
    if (r.reversible === true) return 'Has a dispute route';
    if (r.reversible === false) return 'No chargeback once sent';
    return 'Depends how you send it';
  }, []);

  const rows = mode === 'pay' ? rails : carriers;
  const empty = state === 'ok' && (rows?.length ?? 0) === 0;

  return (
    <BottomSheetModal
      visible={visible}
      onClose={onClose}
      title={mode === 'pay' ? 'Pay the seller' : 'Book the parcel'}
      colors={colors}
      maxHeight="80%"
    >
      <ScrollView contentContainerStyle={styles.sheet} keyboardShouldPersistTaps="handled">
        {mode === 'pay' ? (
          <View style={[styles.amountBox, { borderColor: colors.border }]}>
            <Text style={[styles.amountCaption, { color: colors.muted }]}>Agreed amount</Text>
            {/* Selectable, not a copy button: expo-clipboard is not installed,
                and a guarded require of a missing package no-ops silently on
                BOTH platforms. */}
            <Text selectable style={[styles.amountValue, { color: colors.text }]}>
              {amountLabel}
            </Text>
          </View>
        ) : null}

        {state === 'loading' ? (
          <Text style={[styles.hint, { color: colors.muted }]}>Loading…</Text>
        ) : state === 'error' ? (
          <View style={styles.errorRow}>
            <Text style={[styles.hint, { color: colors.muted }]}>Couldn&apos;t load that list.</Text>
            <AnimatedPressable
              onPress={() => setRetryNonce((n) => n + 1)}
              accessibilityRole="button"
              accessibilityLabel="Try again"
            >
              <Text style={[styles.link, { color: colors.accent }]}>Try again</Text>
            </AnimatedPressable>
          </View>
        ) : empty ? (
          <Text style={[styles.hint, { color: colors.muted }]}>
            {mode === 'pay'
              ? 'No rails listed for your region yet. Agree a method with the seller in chat.'
              : 'No carriers with an online booking page for your region yet.'}
          </Text>
        ) : mode === 'pay' ? (
          // Rendered in the ORDER THE SERVER GAVE (alphabetical). Do not sort,
          // pin or highlight — any order we impose is a statement about which
          // provider we prefer, which §5a forbids.
          (rails ?? []).map((r) => (
            <AnimatedPressable
              key={r.key}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                openUrl(r.url);
              }}
              style={[styles.row, { borderColor: colors.border }]}
              accessibilityRole="link"
              accessibilityLabel={`Open ${r.label}`}
            >
              <View style={{ flex: 1 }}>
                <Text style={[styles.rowTitle, { color: colors.text }]}>{r.label}</Text>
                <Text style={[styles.rowMeta, { color: colors.muted }]}>
                  {r.coverage} · {reversibilityLabel(r)}
                </Text>
                {r.note ? (
                  <Text style={[styles.rowNote, { color: colors.muted }]}>{r.note}</Text>
                ) : null}
              </View>
              <Ionicons name="open-outline" size={16} color={colors.muted} />
            </AnimatedPressable>
          ))
        ) : (
          (carriers ?? []).map((c) => (
            <AnimatedPressable
              key={c.key}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                if (c.book_url) openUrl(c.book_url);
              }}
              style={[styles.row, { borderColor: colors.border }]}
              accessibilityRole="link"
              accessibilityLabel={`Book with ${c.label}`}
            >
              <View style={{ flex: 1 }}>
                <Text style={[styles.rowTitle, { color: colors.text }]}>{c.label}</Text>
                <Text style={[styles.rowMeta, { color: colors.muted }]}>
                  You book and pay {c.label} directly
                </Text>
              </View>
              <Ionicons name="open-outline" size={16} color={colors.muted} />
            </AnimatedPressable>
          ))
        )}

        {/* Every time the list is shown, not once at onboarding. This sentence
            is what keeps the screen a directory rather than a service. */}
        <Text style={[styles.disclaimer, { color: colors.muted }]}>
          {mode === 'pay'
            ? disclaimer ||
              'Sparrow does not process, hold or verify payments. You pay the seller directly through your own provider, and any dispute is handled by that provider, not by Sparrow.'
            : 'You buy carriage from the carrier in your own name. Sparrow does not book, insure or guarantee shipments, and marking the trade complete stays something you and the buyer each do by hand.'}
        </Text>
      </ScrollView>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  sheet: { padding: 16, paddingBottom: 32, gap: 10 },
  amountBox: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  amountCaption: {
    fontSize: textToken.sm,
    fontWeight: fontWeight.bold,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  amountValue: { fontSize: textToken.xl, fontWeight: fontWeight.extrabold, marginTop: 2 },
  hint: { fontSize: textToken.md, lineHeight: 20 },
  link: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
  rowTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  rowMeta: { fontSize: textToken.sm, marginTop: 2 },
  rowNote: { fontSize: textToken.sm, marginTop: 3, fontStyle: 'italic' },
  disclaimer: { fontSize: textToken.sm, lineHeight: 17, marginTop: 6 },
});
