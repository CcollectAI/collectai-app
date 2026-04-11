/**
 * Register screen — username + email + password sign-up.
 * Pro-grade: gradient bg, floating-label inputs, animated strength bar, animated checkbox.
 */

import React, { useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
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
import { BlurView } from 'expo-blur';
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { useStaggerReveal } from '@/motion/useStaggerReveal';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { track } from '@/analytics/track';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { AuthTextInput } from '@/components/auth/AuthTextInput';
import { fonts } from '@/theme/tokens';

function RegisterScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const { colors, isDark } = useAppTheme();
  const { showToast } = useToast();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  const { getItemStyle } = useStaggerReveal({ count: 6, staggerMs: 60 });

  // Animated checkbox
  const checkScale = useRef(new Animated.Value(0)).current;
  const toggleTerms = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const next = !termsAccepted;
    setTermsAccepted(next);
    Animated.spring(checkScale, {
      toValue: next ? 1 : 0,
      friction: 6,
      tension: 100,
      useNativeDriver: true,
    }).start();
  };

  // Animated strength bar
  const strengthAnim = useRef(new Animated.Value(0)).current;
  const prevPercent = useRef(0);

  const getPasswordStrength = (pw: string): { label: string; percent: number; color: string } => {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;

    if (score <= 1) return { label: t('auth.password_strength.weak'), percent: 20, color: colors.danger };
    if (score === 2) return { label: t('auth.password_strength.fair'), percent: 40, color: '#F59E0B' };
    if (score === 3) return { label: t('auth.password_strength.good'), percent: 60, color: '#F59E0B' };
    if (score === 4) return { label: t('auth.password_strength.strong'), percent: 80, color: '#22C55E' };
    return { label: t('auth.password_strength.excellent'), percent: 100, color: '#22C55E' };
  };

  const handlePasswordChange = (pw: string) => {
    setPassword(pw);
    if (pw.length > 0) {
      const { percent } = getPasswordStrength(pw);
      if (percent !== prevPercent.current) {
        prevPercent.current = percent;
        Animated.spring(strengthAnim, {
          toValue: percent / 100,
          friction: 8,
          tension: 60,
          useNativeDriver: false,
        }).start();
      }
    } else {
      prevPercent.current = 0;
      strengthAnim.setValue(0);
    }
  };

  async function handleSignUp() {
    if (!termsAccepted) {
      showToast({ message: t('auth.errors.accept_terms'), type: 'warning' });
      return;
    }

    const trimmedUsername = username.trim();
    const trimmedEmail = email.trim();

    if (!trimmedUsername || !trimmedEmail || !password) {
      showToast({ message: t('auth.errors.fill_all_fields'), type: 'warning' });
      return;
    }

    if (password.length < 8) {
      showToast({ message: t('auth.errors.password_min_length'), type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({
        email: trimmedEmail,
        password,
      });
      if (error) throw error;

      const user = data.user;
      if (!user) {
        showToast({ message: t('auth.errors.sign_up_no_user'), type: 'error' });
        return;
      }

      // Create profile immediately so the row exists regardless of email-verify path.
      // upsert (id PK) makes this idempotent if a Supabase trigger also creates it.
      const { error: profileError } = await supabase
        .from('profiles')
        .upsert({ id: user.id, username: trimmedUsername }, { onConflict: 'id' });
      if (profileError) {
        const code = (profileError as { code?: string }).code;
        if (code === '23505') {
          // Username unique violation — auth account exists but profile doesn't.
          // Surface to user and let them retry with a different username.
          showToast({ message: t('auth.errors.username_taken'), type: 'warning' });
          return;
        }
        // Don't strand the user with an auth account but no profile — log and continue.
        // The post-verify flow will retry profile creation on first sign-in.
        // eslint-disable-next-line no-console
        console.warn('[register] profile upsert failed', code, profileError);
      }

      track({ name: 'user_signed_up', properties: { method: 'email' } });

      if (!user.email_confirmed_at) {
        router.replace({
          pathname: '/(auth)/verify-email',
          params: { email: trimmedEmail },
        });
        return;
      }
      router.replace('/(auth)/onboarding');
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : t('auth.errors.sign_up_failed'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  const strength = password.length > 0 ? getPasswordStrength(password) : null;

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
            {/* Brand */}
            <Animated.View style={[styles.brandSection, getItemStyle(0)]}>
              <View style={[styles.iconCircleOuter, { backgroundColor: colors.brand.base + '15' }]}>
                {Platform.OS === 'ios' ? (
                  <BlurView intensity={40} tint={isDark ? 'dark' : 'light'} style={styles.iconCircle}>
                    <Ionicons name="person-add-outline" size={36} color={colors.brand.dark} />
                  </BlurView>
                ) : (
                  <View style={[styles.iconCircle, { backgroundColor: colors.brand.base + '25' }]}>
                    <Ionicons name="person-add-outline" size={36} color={colors.brand.dark} />
                  </View>
                )}
              </View>
              <Text style={[styles.brandTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                {t('auth.register.title')}
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>
                {t('auth.register.subtitle')}
              </Text>
            </Animated.View>

            {/* Form */}
            <View style={styles.form}>
              <Animated.View style={getItemStyle(1)}>
                <AuthTextInput
                  label="Username"
                  icon="person-outline"
                  value={username}
                  onChangeText={setUsername}
                  autoCapitalize="none"
                  autoComplete="username-new"
                  autoFocus
                  returnKeyType="next"
                  onSubmitEditing={() => emailRef.current?.focus()}
                />
              </Animated.View>

              <Animated.View style={[{ marginTop: 14 }, getItemStyle(2)]}>
                <AuthTextInput
                  ref={emailRef}
                  label="Email"
                  icon="mail-outline"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoComplete="email"
                  returnKeyType="next"
                  onSubmitEditing={() => passwordRef.current?.focus()}
                />
              </Animated.View>

              <Animated.View style={[{ marginTop: 14 }, getItemStyle(3)]}>
                <AuthTextInput
                  ref={passwordRef}
                  label="Password"
                  icon="lock-closed-outline"
                  value={password}
                  onChangeText={handlePasswordChange}
                  secureTextEntry
                  autoComplete="new-password"
                  returnKeyType="done"
                  onSubmitEditing={handleSignUp}
                />

                {/* Animated password strength bar */}
                {password.length > 0 && strength && (
                  <View style={styles.strengthContainer}>
                    <View style={[styles.strengthBarBg, { backgroundColor: colors.border }]}>
                      <Animated.View
                        style={[
                          styles.strengthBarFill,
                          {
                            backgroundColor: strength.color,
                            width: strengthAnim.interpolate({
                              inputRange: [0, 1],
                              outputRange: ['0%', '100%'],
                            }),
                          },
                        ]}
                      />
                    </View>
                    <Text style={[styles.strengthLabel, { color: strength.color }]}>
                      {strength.label}
                    </Text>
                  </View>
                )}
              </Animated.View>

              <Animated.View style={getItemStyle(4)}>
                <AnimatedPressable
                  style={styles.gradientBtnWrap}
                  onPress={handleSignUp}
                  disabled={loading}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.register.create_button')}
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
                      <Text style={styles.gradientBtnText}>{t('auth.register.create_button')}</Text>
                    )}
                  </LinearGradient>
                </AnimatedPressable>

                {/* Animated Terms checkbox */}
                <AnimatedPressable
                  style={styles.termsRow}
                  onPress={toggleTerms}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: termsAccepted }}
                  accessibilityLabel={t('auth.errors.accept_terms')}
                >
                  <View
                    style={[
                      styles.checkbox,
                      {
                        borderColor: termsAccepted ? colors.brand.base : colors.border,
                        backgroundColor: termsAccepted ? colors.brand.base : 'transparent',
                      },
                    ]}
                  >
                    <Animated.View style={{ transform: [{ scale: checkScale }] }}>
                      <Ionicons name="checkmark" size={14} color="#FFFFFF" />
                    </Animated.View>
                  </View>
                  <Text style={[styles.termsText, { color: colors.muted }]}>
                    {t('auth.register.i_agree_to')}{' '}
                    <Text
                      style={[styles.legalLink, { color: colors.brand.dark }]}
                      onPress={() => router.push('/legal/terms')}
                      accessibilityRole="link"
                    >
                      {t('auth.register.terms_of_service')}
                    </Text>
                    {' '}{t('auth.register.and')}{' '}
                    <Text
                      style={[styles.legalLink, { color: colors.brand.dark }]}
                      onPress={() => router.push('/legal/privacy-policy')}
                      accessibilityRole="link"
                    >
                      {t('auth.register.privacy_policy')}
                    </Text>
                  </Text>
                </AnimatedPressable>
              </Animated.View>
            </View>

            {/* Footer */}
            <Animated.View style={getItemStyle(5)}>
              <AnimatedPressable
                style={styles.footer}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push('/(auth)/login');
                }}
                accessibilityRole="link"
                accessibilityLabel={t('auth.register.sign_in_instead')}
              >
                <Text style={[styles.footerText, { color: colors.muted }]}>
                  {t('auth.already_have_account')}{' '}
                  <Text style={{ color: colors.brand.dark, fontWeight: '600' }}>{t('auth.sign_in')}</Text>
                </Text>
              </AnimatedPressable>
            </Animated.View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function RegisterScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Register">
      <RegisterScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 40,
  },
  brandSection: {
    alignItems: 'center',
    marginBottom: 40,
  },
  iconCircleOuter: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  iconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  brandTitle: {
    fontSize: 28,
    fontWeight: '800',
  },
  brandSubtitle: {
    fontSize: 16,
    marginTop: 4,
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
  termsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 20,
    paddingHorizontal: 4,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  termsText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 20,
  },
  legalLink: {
    fontWeight: '600',
  },
  strengthContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
  },
  strengthBarBg: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  strengthBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  strengthLabel: {
    fontSize: 12,
    fontWeight: '600',
    minWidth: 60,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  footerText: {
    fontSize: 14,
  },
});
