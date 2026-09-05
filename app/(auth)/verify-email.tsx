/**
 * Verify Email screen — shown after registration to guide users to check their inbox.
 * Pro-grade: gradient bg, pulsing email icon, enter reveal, gradient button.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { useEnterReveal } from '@/motion/useEnterReveal';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { fonts } from '@/theme/tokens';

/** Supabase's own cooldown between confirmation sends, in seconds. */
export const RESEND_COOLDOWN_S = 60;

/**
 * Seconds to wait, if `e` is Supabase's send-rate-limit error; otherwise null.
 *
 * Prefers the server's own number — it reports the REMAINING wait ("you can
 * only request this after 13 seconds"), so a hardcoded 60 would over-state the
 * wait every time. Falls back to the full cooldown when the wording changes,
 * which is still far better than the silence this replaces.
 */
export function rateLimitSeconds(e: unknown): number | null {
  const err = e as { status?: number; code?: string; message?: string } | null;
  if (!err) return null;
  const isRateLimit =
    err.status === 429 ||
    err.code === 'over_email_send_rate_limit' ||
    /rate limit/i.test(err.message ?? '');
  if (!isRateLimit) return null;
  const m = /after (\d+) second/i.exec(err.message ?? '');
  const parsed = m ? parseInt(m[1], 10) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : RESEND_COOLDOWN_S;
}

function VerifyEmailScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { email } = useLocalSearchParams<{ email: string }>();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  // Starts at 60, not 0. The ONLY route to this screen is a successful
  // signUp in register.tsx, which has just sent the confirmation email — and
  // Supabase enforces a 60s cooldown from that send. Starting at 0 rendered an
  // enabled "Resend email" button whose every tap was guaranteed to 429 for
  // the first minute. Measured against prod 2026-09-05: resend at +0s said
  // "after 58 seconds", at +45s "after 13 seconds", and only succeeded past
  // 60s (then genuinely delivered a 2nd email).
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_S);

  const { animatedStyle: contentReveal } = useEnterReveal({ fromY: 16 });

  // Pulsing email icon
  const pulseScale = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseScale, { toValue: 1.05, duration: 1000, useNativeDriver: true }),
        Animated.timing(pulseScale, { toValue: 1.0, duration: 1000, useNativeDriver: true }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, []);

  async function handleResend() {
    if (!email) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setResending(true);
    try {
      const { error } = await supabase.auth.resend({ type: 'signup', email });
      if (error) throw error;
      setResent(true);
      setCooldown(RESEND_COOLDOWN_S);
    } catch (e) {
      // A rate-limit is NOT an enumeration signal and must not be swallowed.
      //
      // Every error used to land in a bare `catch {}`, so a 429 left `resent`
      // false and `cooldown` 0: the user tapped "Resend email" and absolutely
      // nothing happened — no confirmation, no error, no countdown — so they
      // tapped again, and again. On the one screen whose entire job is "your
      // email is on its way", silence is the worst possible answer.
      //
      // The enumeration defence still holds. It protects against revealing
      // whether an ADDRESS EXISTS; a 429 reveals only that *this device* asked
      // too recently, which the user already knows because they just signed
      // up. Supabase also defends this server-side (register.tsx relies on the
      // empty-`identities` tell for the same reason).
      const secs = rateLimitSeconds(e);
      if (secs !== null) {
        setCooldown(secs);
      }
      // Everything else stays silent, deliberately — see above.
    } finally {
      setResending(false);
    }
  }

  // Auto-detect email verification by polling auth session
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (data.session?.user?.email_confirmed_at) {
          clearInterval(interval);
          router.replace('/(auth)/onboarding');
        }
      } catch {
        // best-effort: 5s poll for verification status. A single failed tick is
        // meaningless and logging each one would flood the log at 12/min; the
        // next tick retries.
      }
    }, 5000);
    const timeout = setTimeout(() => clearInterval(interval), 300000);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  return (
    <GradientBackground>
      <SafeAreaView style={styles.safe}>
        <Animated.View style={[styles.container, contentReveal]}>
          {/* Pulsing Icon */}
          <Animated.View
            style={[
              styles.iconCircle,
              { backgroundColor: colors.brand.base + '20', transform: [{ scale: pulseScale }] },
            ]}
          >
            <Ionicons name="mail-unread-outline" size={48} color={colors.brand.dark} />
          </Animated.View>

          <Text style={[styles.title, { color: colors.text, fontFamily: fonts.bold }]}>
            {t('auth.verify.title')}
          </Text>

          <Text style={[styles.description, { color: colors.muted }]}>
            {t('auth.verify.description')}{'\n'}
            <Text style={[styles.emailText, { color: colors.text }]}>{email || t('auth.verify.email_fallback')}</Text>
          </Text>

          <Text style={[styles.hint, { color: colors.muted }]}>
            {t('auth.verify.hint')}
          </Text>

          {/* Resend */}
          {resending ? (
            <ActivityIndicator size="small" color={colors.brand.base} style={{ marginTop: 32 }} />
          ) : cooldown > 0 ? (
            <View style={styles.cooldownBadge}>
              <Text style={[styles.cooldownText, { color: colors.muted }]}>
                {t('auth.verify.resend_cooldown', { seconds: cooldown })}
              </Text>
            </View>
          ) : resent ? (
            <AnimatedPressable
              style={styles.resendBtn}
              onPress={handleResend}
              accessibilityRole="button"
              accessibilityLabel={t('auth.verify.resend_email')}
            >
              <Ionicons name="checkmark-circle" size={18} color={colors.brand.dark} />
              <Text style={[styles.resendText, { color: colors.brand.dark }]}>
                {t('auth.verify.resent_tap_again')}
              </Text>
            </AnimatedPressable>
          ) : (
            <AnimatedPressable
              style={styles.resendBtn}
              onPress={handleResend}
              accessibilityRole="button"
              accessibilityLabel={t('auth.verify.resend_email')}
            >
              <Text style={[styles.resendText, { color: colors.brand.dark }]}>{t('auth.verify.resend_email')}</Text>
            </AnimatedPressable>
          )}

          {/* Go to login */}
          <AnimatedPressable
            style={styles.gradientBtnWrap}
            onPress={() => router.replace('/(auth)/login')}
            accessibilityRole="button"
            accessibilityLabel={t('auth.verify.go_to_sign_in')}
          >
            <LinearGradient
              colors={[colors.brand.dark, colors.brand.base]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.gradientBtn}
            >
              <Text style={styles.gradientBtnText}>{t('auth.verify.go_to_sign_in')}</Text>
            </LinearGradient>
          </AnimatedPressable>

          <Text style={[styles.spamHint, { color: colors.muted }]}>
            {t('auth.verify.spam_hint')}
          </Text>
        </Animated.View>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function VerifyEmailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Verify Email">
      <VerifyEmailScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 8,
  },
  emailText: {
    fontWeight: '700',
  },
  hint: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 8,
  },
  resendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'stretch',
    gap: 6,
    marginTop: 32,
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#44A9A1',
    backgroundColor: '#81D8D015',
    minHeight: 54,
  },
  cooldownBadge: {
    marginTop: 32,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    backgroundColor: '#F5F5F5',
  },
  cooldownText: {
    fontSize: 14,
    fontWeight: '500',
  },
  resendText: {
    fontSize: 15,
    fontWeight: '600',
  },
  gradientBtnWrap: {
    marginTop: 24,
    marginBottom: 8,
    alignSelf: 'stretch',
    borderRadius: 16,
    shadowColor: '#44A9A1',
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  gradientBtn: {
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 54,
  },
  gradientBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: fonts.bold,
  },
  skipBtn: {
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 32,
  },
  skipBtnText: {
    fontSize: 15,
    fontWeight: '600',
    textDecorationLine: 'underline',
  },
  spamHint: {
    fontSize: 13,
    textAlign: 'center',
    marginTop: 16,
  },
});
