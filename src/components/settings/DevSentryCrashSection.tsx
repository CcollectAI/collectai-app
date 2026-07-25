/**
 * DevSentryCrashSection — dev-only buttons that exercise the Sentry
 * pipeline so we can verify integration end-to-end without waiting for
 * a real production crash.
 *
 * Three buttons:
 *   1. Throw uncaught — verifies global error handler + ErrorBoundary
 *   2. captureException — verifies manual capture (with PII scrub)
 *   3. captureMessage — verifies info-level events go through scrub
 *
 * After tapping any button, check https://sentry.io → your project →
 * Issues. The event should appear within ~30s with:
 *   - user: { id: <uuid> }  (no email, per Sentry.setUser scrub)
 *   - extras: any sensitive keys redacted as [REDACTED]
 *   - exception message: emails/JWTs scrubbed inline
 *
 * Production builds hide this section entirely (__DEV__ gate).
 *
 * Added 2026-05-12 as part of the post-launch hygiene pass.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { logger } from '@/lib/logger';

let Sentry: {
  captureException: (e: unknown, ctx?: Record<string, unknown>) => void;
  captureMessage: (msg: string, level?: string) => void;
} | null = null;
try {
  Sentry = require('@sentry/react-native');
} catch (e) {
  logger.error('[silent-catch] DevSentryCrashSection.tsx:33:', e);
  // sentry not installed in dev — no-op
}

export const DevSentryCrashSection: React.FC = () => {
  const { colors } = useAppTheme();

  // Hide in production
  if (typeof __DEV__ !== 'undefined' && !__DEV__) return null;

  const throwUncaught = () => {
    Alert.alert(
      'Throwing uncaught error',
      'The app will likely show the ErrorBoundary screen. Check Sentry in 30s.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Throw',
          style: 'destructive',
          onPress: () => {
            // Defer to next tick so the Alert dismisses first
            setTimeout(() => {
              throw new Error(
                'Sentry test: uncaught error from DevSentryCrashSection (intentional)',
              );
            }, 0);
          },
        },
      ],
    );
  };

  const captureException = () => {
    if (!Sentry) {
      Alert.alert('Sentry not installed', 'No @sentry/react-native module available.');
      return;
    }
    const err = new Error(
      'Sentry test: captureException with PII bait (merle@example.com, sk_live_abcdefghijklmnopqrstuv)',
    );
    Sentry.captureException(err, {
      extra: {
        email: 'should-be-redacted@example.com',
        api_key: 'sk_live_should_redact_test123',
        innocuous: 'this should pass through',
      },
    });
    Alert.alert('Sent', 'Check Sentry Issues — message + extras should be scrubbed.');
  };

  const captureMessage = () => {
    if (!Sentry) {
      Alert.alert('Sentry not installed', 'No @sentry/react-native module available.');
      return;
    }
    Sentry.captureMessage(
      'Sentry test: captureMessage — token in body: eyJabc.def_-Z.ghi_-Z',
      'info',
    );
    Alert.alert('Sent', 'Check Sentry Issues — JWT should be redacted.');
  };

  return (
    <View
      style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}
    >
      <View style={styles.header}>
        <Ionicons name="bug-outline" size={16} color={colors.danger} />
        <Text style={[styles.title, { color: colors.text }]}>Dev: Sentry Test</Text>
        <View style={[styles.devBadge, { backgroundColor: colors.warning + '20' }]}>
          <Text style={[styles.devBadgeText, { color: colors.warning }]}>DEV ONLY</Text>
        </View>
      </View>
      <Text style={[styles.subtitle, { color: colors.muted }]}>
        Verify Sentry integration + PII scrubbing. Events appear in Sentry within 30s.
      </Text>

      <Pressable
        onPress={captureMessage}
        style={[styles.btn, { borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel="Send Sentry test message"
      >
        <Ionicons name="paper-plane-outline" size={14} color={colors.text} />
        <Text style={[styles.btnText, { color: colors.text }]}>
          Send captureMessage (info)
        </Text>
      </Pressable>

      <Pressable
        onPress={captureException}
        style={[styles.btn, { borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel="Send Sentry test exception"
      >
        <Ionicons name="warning-outline" size={14} color={colors.warning} />
        <Text style={[styles.btnText, { color: colors.text }]}>
          Send captureException
        </Text>
      </Pressable>

      <Pressable
        onPress={throwUncaught}
        style={[styles.btn, styles.btnDanger, { borderColor: colors.danger }]}
        accessibilityRole="button"
        accessibilityLabel="Throw uncaught error"
      >
        <Ionicons name="flash-outline" size={14} color={colors.danger} />
        <Text style={[styles.btnText, { color: colors.danger }]}>
          Throw uncaught error
        </Text>
      </Pressable>
    </View>
  );
};

const styles = StyleSheet.create({
  section: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginTop: 12,
    marginBottom: 12,
    gap: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  title: {
    fontSize: 14,
    fontWeight: '700',
    flex: 1,
  },
  devBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  devBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 11,
    marginBottom: 6,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  btnDanger: {
    borderWidth: 1.5,
  },
  btnText: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
});
