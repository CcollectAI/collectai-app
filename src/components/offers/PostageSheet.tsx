/**
 * "Add postage" — the one number Sparrow cannot know about a completed sale.
 *
 * Extracted from app/offers.tsx (2026-09-23) so the trade screen can offer it
 * too. It lived ONLY in the offers list, and only on the "Selling" tab: the
 * default "All" tab renders compact cards whose tap opens /offer/[offerId],
 * which had no postage step — so from where a seller lands, realised P/L's
 * missing number could not be entered (walked on Android 2026-09-23). One
 * component, two callers, so the two cannot drift.
 *
 * `onSave` receives a parsed, non-negative amount. 0 is a real answer (handed
 * over in person); only an unparseable entry is refused.
 */
import React, { useEffect, useState } from 'react';
import { ScrollView, Text, TextInput, StyleSheet } from 'react-native';
import { useTranslation } from 'react-i18next';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { parseMoney } from '@/lib/format';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

type Props = {
  visible: boolean;
  onClose: () => void;
  onSave: (amount: number) => void;
};

export function PostageSheet({ visible, onClose, onSave }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [amount, setAmount] = useState('');

  // A fresh field every time the sheet opens, as the list screen did.
  useEffect(() => {
    if (visible) setAmount('');
  }, [visible]);

  // parseMoney, not Number: a Dutch seller types "7,25" and Number() would read
  // 7 — `npm run check:numbers` enforces this.
  const parsed = parseMoney(amount);
  const valid = parsed !== null && parsed >= 0;

  return (
    <BottomSheetModal
      visible={visible}
      onClose={onClose}
      title={t('offers.add_postage', { defaultValue: 'Add postage' })}
      colors={colors}
      maxHeight="60%"
    >
      <ScrollView contentContainerStyle={styles.sheet} keyboardShouldPersistTaps="handled">
        <Text style={[styles.sheetHint, { color: colors.muted }]}>
          {t('offers.postage_hint', {
            defaultValue:
              "What did it cost you to post it? We can't see this, so your profit is shown before postage until you tell us. Nothing is shared with the buyer.",
          })}
        </Text>

        <Text style={[styles.sheetLabel, { color: colors.text }]}>
          {t('offers.postage_amount', { defaultValue: 'Postage you paid' })}
        </Text>
        <TextInput
          value={amount}
          onChangeText={setAmount}
          placeholder={t('offers.postage_placeholder', { defaultValue: 'e.g. 7,25' })}
          placeholderTextColor={colors.muted}
          keyboardType="decimal-pad"
          maxLength={10}
          style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
          accessibilityLabel={t('offers.postage_amount', { defaultValue: 'Postage you paid' })}
        />
        {/* 0 is a real answer and says so: free postage (local pickup) is NOT
            the same as "not recorded" — that is why the column is nullable. */}
        <Text style={[styles.sheetHint, { color: colors.muted }]}>
          {t('offers.postage_zero_ok', {
            defaultValue: 'Handed it over in person? Enter 0 — that is an answer, not a blank.',
          })}
        </Text>

        <AnimatedPressable
          onPress={() => { if (valid) onSave(parsed as number); }}
          disabled={!valid}
          style={[
            styles.btn,
            styles.sheetSave,
            valid
              ? { backgroundColor: colors.accent }
              : { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
          ]}
          accessibilityRole="button"
          accessibilityState={{ disabled: !valid }}
          accessibilityLabel={t('offers.a11y_save_postage', { defaultValue: 'Save postage' })}
        >
          <Text style={[styles.btnText, { color: valid ? colors.accentText : colors.muted }]}>
            {t('common.save', { defaultValue: 'Save' })}
          </Text>
        </AnimatedPressable>
      </ScrollView>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  sheet: { padding: 16, paddingBottom: 32, gap: 10 },
  sheetHint: { fontSize: textToken.md, lineHeight: 20 },
  sheetLabel: {
    fontSize: textToken.sm, fontWeight: fontWeight.bold,
    textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 8,
  },
  input: {
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 13, fontSize: textToken.lg,
  },
  btn: {
    minHeight: 38, justifyContent: 'center', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: radius.md,
    flexShrink: 1,
  },
  sheetSave: { marginTop: 8, alignItems: 'center', paddingVertical: 13 },
  btnText: { fontSize: textToken.md, fontWeight: fontWeight.bold, textAlign: 'center' },
});
