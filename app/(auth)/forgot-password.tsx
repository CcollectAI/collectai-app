/**
 * Forgot Password screen — sends password reset email via Supabase.
 * Pro-grade: gradient bg, floating-label input, enter reveal, animated success checkmark.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
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
import { useToast } from '@/components/Toast';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { AuthTextInput } from '@/components/auth/AuthTextInput';
import { fonts } from '@/theme/tokens';

function ForgotPasswordScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const { animatedStyle: brandReveal } = useEnterReveal({ fromY: 16 });

  // Animated success checkmark
  const checkScale = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (sent) {
      Animated.spring(checkScale, {
        toValue: 1,
        friction: 5,
        tension: 60,
        useNativeDriver: true,
      }).start();
    } else {
      checkScale.setValue(0);
    }
  }, [sent]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function handleReset() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      showToast({ message: t('auth.errors.reset_email_required'), type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(trimmedEmail, {
        // https Universal-Link page (avoids Safari's "address invalid" on a raw
        // custom scheme). It forwards the #access_token fragment (type=recovery)
        // to sparrow://, and AuthProvider's handler routes recovery → reset-password.
        redirectTo: 'https://sparrowcollect.com/auth/confirm',
      });
      if (error) throw error;
      setSent(true);
      setCooldown(60);
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : t('auth.errors.reset_failed'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <GradientBackground>
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.scroll}
            keyboardShouldPersistTaps="handled"
          >
            {/* Back button */}
            <AnimatedPressable
              style={styles.backBtn}
              onPress={() => router.back()}
              accessibilityRole="button"
              accessibilityLabel={t('common.back')}
            >
              <Ionicons name="arrow-back" size={24} color={colors.text} />
            </AnimatedPressable>

            {/* Brand */}
            <Animated.View style={[styles.brandSection, brandReveal]}>
              <View style={[styles.iconCircle, { backgroundColor: colors.brand.base + '20' }]}>
                <Ionicons name="key-outline" size={32} color={colors.brand.dark} />
              </View>
              <Text style={[styles.brandTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                {t('auth.forgot.title')}
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>
                {sent ? t('auth.forgot.subtitle_sent') : t('auth.forgot.subtitle')}
              </Text>
            </Animated.View>

            {sent ? (
              <View style={styles.successSection}>
                <Animated.View style={{ transform: [{ scale: checkScale }] }}>
                  <Ionicons name="checkmark-circle" size={56} color={colors.success} />
                </Animated.View>
                <Text style={[styles.successText, { color: colors.text }]}>
                  {t('auth.forgot.success_text')}{'\n'}
                  <Text style={{ fontWeight: '700' }}>{email.trim()}</Text>
                </Text>
                <Text style={[styles.successHint, { color: colors.muted }]}>
                  {t('auth.forgot.success_hint')}
                </Text>

                <AnimatedPressable
                  style={[styles.gradientBtnWrap, cooldown > 0 && { opacity: 0.6 }]}
                  onPress={() => {
                    if (cooldown > 0) return;
                    setSent(false);
                    setEmail('');
                  }}
                  disabled={cooldown > 0}
                  accessibilityRole="button"
                  accessibilityLabel={
                    cooldown > 0 ? t('auth.forgot.try_again_cooldown', { seconds: cooldown }) : t('auth.forgot.try_again')
                  }
                >
                  <LinearGradient
                    colors={[colors.brand.dark, colors.brand.base]}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.gradientBtn}
                  >
                    <Text style={styles.gradientBtnText}>
                      {cooldown > 0
                        ? t('auth.forgot.try_again_cooldown', { seconds: cooldown })
                        : t('auth.forgot.try_again')}
                    </Text>
                  </LinearGradient>
                </AnimatedPressable>

                <AnimatedPressable
                  style={[styles.secondaryBtn, { borderColor: colors.border }]}
                  onPress={() => router.replace('/(auth)/login')}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.forgot.back_to_sign_in')}
                >
                  <Text style={[styles.secondaryBtnText, { color: colors.brand.dark }]}>
                    {t('auth.forgot.back_to_sign_in')}
                  </Text>
                </AnimatedPressable>
              </View>
            ) : (
              <View style={styles.form}>
                <AuthTextInput
                  label={t('auth.email')}
                  icon="mail-outline"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoComplete="email"
                  autoFocus
                  returnKeyType="send"
                  onSubmitEditing={handleReset}
                />

                <AnimatedPressable
                  style={styles.gradientBtnWrap}
                  onPress={handleReset}
                  disabled={loading}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.forgot.send_reset_link')}
                >
                  <LinearGradient
                    colors={[colors.brand.dark, colors.brand.base]}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.gradientBtn}
                  >
                    {loading ? (
                      <ActivityIndicator color="#FFFFFF" />
                    ) : (
                      <Text style={styles.gradientBtnText}>{t('auth.forgot.send_reset_link')}</Text>
                    )}
                  </LinearGradient>
                </AnimatedPressable>

                <AnimatedPressable
                  style={styles.footer}
                  onPress={() => router.back()}
                  accessibilityRole="link"
                  accessibilityLabel={t('auth.forgot.back_to_sign_in')}
                >
                  <Text style={[styles.footerText, { color: colors.muted }]}>
                    {t('auth.forgot.remember_password')}{' '}
                    <Text style={{ color: colors.brand.dark, fontWeight: '600' }}>{t('auth.sign_in')}</Text>
                  </Text>
                </AnimatedPressable>
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function ForgotPasswordScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Forgot Password">
      <ForgotPasswordScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingVertical: 40,
  },
  backBtn: {
    padding: 4,
    marginBottom: 16,
    alignSelf: 'flex-start',
  },
  brandSection: {
    alignItems: 'center',
    marginBottom: 40,
  },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  brandTitle: {
    fontSize: 28,
    fontWeight: '800',
  },
  brandSubtitle: {
    fontSize: 15,
    marginTop: 8,
    textAlign: 'center',
    lineHeight: 22,
  },
  form: {
    marginBottom: 32,
  },
  gradientBtnWrap: {
    marginTop: 24,
    borderRadius: 16,
    shadowColor: '#44A9A1',
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
    alignSelf: 'stretch',
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
  secondaryBtn: {
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: 'center',
    alignSelf: 'stretch',
    marginTop: 12,
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  footerText: {
    fontSize: 14,
  },
  successSection: {
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  successText: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
    marginTop: 16,
    marginBottom: 8,
  },
  successHint: {
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 32,
  },
});
