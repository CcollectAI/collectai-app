/**
 * Diagnostics — reads the retained log ring buffer on the device.
 *
 * WHY THIS EXISTS
 *
 * `src/lib/logger.ts` has retained every log line in a bounded ring buffer
 * since the two loggers were collapsed into one, and its own comment said the
 * buffer was "readable via getRecentLogs() from the diagnostics screen".
 * There was no diagnostics screen. Repo-wide, `getRecentLogs` appeared only in
 * comments, tests and test mocks — captured, correct, and reachable from
 * nowhere, which is the house failure mode.
 *
 * The cost was concrete. `app/subscription.tsx` logs exactly one line naming
 * which of three causes made the paywall unavailable ("reason=no-key" /
 * "configure-failed" / "no-offering"), deliberately at `logger.error` because
 * release builds strip info/warn. On a TestFlight device that line could not
 * be read without plugging the phone into a Mac and opening Console.app, so
 * the paywall was triaged by guesswork across several sessions.
 *
 * Two fixes, this is the second: `app/_layout.tsx` now forwards errors to
 * Sentry, and this screen shows them on the device itself. Sentry needs a
 * network and a DSN; this does not, which matters when the thing being
 * diagnosed IS the network.
 *
 * NOTES ON THE SHAPE (see docs/ui-playbook.md)
 *  - No SafeAreaView: `app/_layout.tsx` sets `headerShown: true` globally and
 *    this screen keeps that header, so insets come from it — same as
 *    analytics.tsx and subscription.tsx, which have none and are correct.
 *  - A plain ScrollView, not FlashList: the buffer is capped at 300 entries so
 *    there is nothing to virtualise, and FlashList v2 absolutely-positions
 *    ListHeaderComponent, which has already cost us a header that rendered
 *    correctly and took no touches.
 *  - `accessibilityRole="button"` only: an iOS-only role value is an
 *    uncatchable FATAL EXCEPTION on Android, not a no-op.
 *  - No fetch, so no skeleton, no timeout and no auth gate to get wrong.
 */
import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Share, Animated } from 'react-native';
import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Ionicons } from '@expo/vector-icons';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useToast } from '@/components/Toast';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { getRecentLogs, clearRecentLogs, logger, type RetainedLog } from '@/lib/logger';

/** Share payloads have a practical size limit; keep the newest entries. */
const SHARE_MAX_ENTRIES = 120;

function DiagnosticsContent() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const [errorsOnly, setErrorsOnly] = useState(true);
  // The buffer keeps filling while this screen is open. `nonce` is bumped by
  // refresh/clear so the memo re-reads it: the buffer is a module-level array,
  // so nothing else would ever tell React that it changed.
  const [nonce, setNonce] = useState(0);

  const levelColor = useCallback(
    (level: RetainedLog['level']): string => {
      switch (level) {
        case 'error':
          return colors.danger;
        case 'warn':
          return colors.warning;
        case 'info':
          return colors.info;
        default:
          return colors.muted;
      }
    },
    [colors],
  );

  const entries = useMemo(() => {
    void nonce;
    // Newest first: the line you came here for is the one that just happened.
    return getRecentLogs(errorsOnly ? 'error' : 'debug').slice().reverse();
  }, [errorsOnly, nonce]);

  const refresh = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setNonce((n) => n + 1);
  }, [settings.hapticsEnabled]);

  const onClear = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    clearRecentLogs();
    setNonce((n) => n + 1);
    showToast({ message: t('diagnostics.cleared'), type: 'success' });
  }, [settings.hapticsEnabled, showToast, t]);

  const onShare = useCallback(async () => {
    const slice = entries.slice(0, SHARE_MAX_ENTRIES);
    if (slice.length === 0) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const body = slice.map((l) => `${l.at} [${l.level}] ${l.message}`).join('\n');
    try {
      await Share.share({ message: body });
    } catch (e) {
      // Not a silent catch. If the one export path fails, this screen is
      // decorative and the user needs to be told rather than left tapping.
      logger.error('[diagnostics] share failed:', e);
      showToast({ message: t('diagnostics.share_failed'), type: 'error' });
    }
  }, [entries, settings.hapticsEnabled, showToast, t]);

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          headerTitle: t('diagnostics.title'),
          headerBackTitle: t('diagnostics.back_title'),
        }}
      />
      <Animated.View
        style={[styles.fill, settings.animationsEnabled ? animatedStyle : undefined]}
      >
        <View style={styles.toolbar}>
          <View style={styles.filters}>
            {([true, false] as const).map((only) => {
              const active = errorsOnly === only;
              const label = only
                ? t('diagnostics.filter_errors')
                : t('diagnostics.filter_all');
              return (
                <AnimatedPressable
                  key={String(only)}
                  onPress={() => setErrorsOnly(only)}
                  style={[
                    styles.chip,
                    {
                      backgroundColor: active ? colors.accent : 'transparent',
                      borderColor: active ? colors.accent : colors.border,
                    },
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  accessibilityLabel={label}
                >
                  {/* colors.accentText, never '#fff': in high-contrast dark the
                      accent fill is white and a hardcoded white label vanishes. */}
                  <Text
                    style={[
                      styles.chipText,
                      { color: active ? colors.accentText : colors.text },
                    ]}
                  >
                    {label}
                  </Text>
                </AnimatedPressable>
              );
            })}
          </View>

          <View style={styles.actions}>
            <AnimatedPressable
              onPress={refresh}
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel={t('diagnostics.refresh')}
            >
              <Ionicons name="refresh" size={18} color={colors.muted} />
            </AnimatedPressable>
            <AnimatedPressable
              onPress={onShare}
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel={t('diagnostics.share')}
            >
              <Ionicons name="share-outline" size={18} color={colors.muted} />
            </AnimatedPressable>
            <AnimatedPressable
              onPress={onClear}
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel={t('diagnostics.clear')}
            >
              <Ionicons name="trash-outline" size={18} color={colors.muted} />
            </AnimatedPressable>
          </View>
        </View>

        <Text style={[styles.subtitle, { color: colors.muted }]}>
          {t('diagnostics.entries', { count: entries.length })}
        </Text>

        {entries.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="checkmark-circle-outline" size={40} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>
              {t('diagnostics.empty_title')}
            </Text>
            <Text style={[styles.emptyBody, { color: colors.muted }]}>
              {t('diagnostics.empty_body')}
            </Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.listContent}>
            {entries.map((l, i) => (
              <View key={`${l.at}-${i}`} style={[styles.row, { borderColor: colors.border }]}>
                <View style={styles.rowHead}>
                  <Text style={[styles.level, { color: levelColor(l.level) }]}>
                    {l.level.toUpperCase()}
                  </Text>
                  <Text style={[styles.time, { color: colors.muted }]}>{l.at}</Text>
                </View>
                <Text style={[styles.message, { color: colors.text }]} selectable>
                  {l.message}
                </Text>
              </View>
            ))}
          </ScrollView>
        )}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  fill: { flex: 1 },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    // 16 is the screen gutter (docs/ui-playbook.md). Subscription used 20 and
    // sat 4pt narrower per side than every other screen.
    paddingHorizontal: 16,
    paddingTop: 12,
    gap: 12,
  },
  filters: { flexDirection: 'row', gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  chipText: { fontSize: textToken.sm, fontWeight: fw.semibold },
  actions: { flexDirection: 'row', gap: 4 },
  iconBtn: { padding: 8 },
  subtitle: {
    fontSize: textToken.sm,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 4,
  },
  listContent: { paddingHorizontal: 16, paddingBottom: 40, gap: 8 },
  row: { borderWidth: 1, borderRadius: radius.md, padding: 10, gap: 4 },
  rowHead: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  // `sm`, not `xs`: the app's xs is 10pt and 10pt is not readable
  // (docs/ui-playbook.md, type-scale section).
  level: { fontSize: textToken.sm, fontWeight: fw.bold },
  time: { fontSize: textToken.sm },
  message: { fontSize: textToken.sm, lineHeight: 18 },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyTitle: { fontSize: textToken.lg, fontWeight: fw.semibold },
  emptyBody: { fontSize: textToken.sm, textAlign: 'center', lineHeight: 20 },
});

export default function DiagnosticsScreen() {
  return (
    <ScreenErrorBoundary screenName="Diagnostics">
      <DiagnosticsContent />
    </ScreenErrorBoundary>
  );
}
