/**
 * The buyer's "I received it", the way Vinted asks it (2026-10-16).
 *
 * Walked as a buyer: one tap on "I received it" completed the trade — the
 * item moved collections, the sale was booked, rating unlocked — with no
 * second look, and nothing undoes it. Vinted gives the buyer two answers:
 * "Everything is OK" (stated as irreversible) and "I have an issue" (talk to
 * the seller first). We copy the QUESTION, not Vinted's 2-day auto-complete:
 * completing a trade from time or carrier status is the trap
 * docs/P2P_MARKETPLACE_SPEC.md §5b rules out — only the buyer confirms.
 *
 * Three buttons: Android's Alert shows at most three
 * (check:android-alert-buttons).
 */
import { Alert } from 'react-native';
import type { TFunction } from 'i18next';

export function askBuyerToConfirmReceipt(opts: {
  t: TFunction;
  onEverythingOk: () => void;
  onIssue: () => void;
}): void {
  const { t } = opts;
  Alert.alert(
    t('receipt.title', { defaultValue: 'Is everything OK with the item?' }),
    t('receipt.body', {
      defaultValue:
        "Confirming completes the trade and can't be undone. Check the item first. If something is wrong, tell the seller before you confirm.",
    }),
    [
      { text: t('receipt.issue', { defaultValue: 'I have an issue' }), onPress: opts.onIssue },
      { text: t('receipt.not_yet', { defaultValue: 'Not yet' }), style: 'cancel' },
      { text: t('receipt.ok', { defaultValue: 'Everything is OK' }), onPress: opts.onEverythingOk },
    ],
  );
}
