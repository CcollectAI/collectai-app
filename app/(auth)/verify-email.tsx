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

function VerifyEmailScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { email } = useLocalSearchParams<{ email: string }>();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

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
      setCooldown(60);
    } catch {
      // Silently fail — don't leak whether the email exists
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
      } catch {}
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
    gap: 6,
    marginTop: 32,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#44A9A1',
    backgroundColor: '#81D8D015',
    minHeight: 44,
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
