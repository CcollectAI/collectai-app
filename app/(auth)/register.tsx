/**
 * Register screen — username + email + password sign-up.
 * Pro-grade: gradient bg, floating-label inputs, animated strength bar, animated checkbox.
 */

import React, { useEffect, useRef, useState } from 'react';
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
import { getPendingReferralCode, clearPendingReferralCode } from '@/lib/referral';
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
  const [referralCode, setReferralCode] = useState('');
  const [codeFromLink, setCodeFromLink] = useState(false);

  // Prefill from a creator link captured by the deep-link handler
  // (src/lib/referral.ts). Without this the code is stored and never read —
  // the user would have to retype what they already clicked.
  useEffect(() => {
    let alive = true;
    getPendingReferralCode().then((code) => {
      if (alive && code) {
        setReferralCode(code);
        setCodeFromLink(true);
      }
    });
    return () => { alive = false; };
  }, []);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  // Stagger animation disabled 2026-05-17 — caused untappable password field on real device.
  const { getItemStyle } = useStaggerReveal({ count: 6, staggerMs: 60, enabled: false });

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
    // Normalise here to match the trigger's UPPER(TRIM(...)), so the code the
    // creator prints and the code we store are the same string.
    const trimmedReferralCode = referralCode.trim().toUpperCase();

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
        options: {
          // Confirmation link redirects to the deployed https Universal-Link page
          // (web/auth/confirm, AASA path /auth/*). Unlike a raw sparrow:// custom
          // scheme — which Safari rejects with "address invalid" from an email
          // redirect — this loads cleanly, then forwards Supabase's #access_token
          // fragment to sparrow://, which the AuthProvider deep-link handler turns
          // into a session. Shows a branded fallback page if the app isn't installed.
          emailRedirectTo: 'https://sparrowcollect.com/auth/confirm',
          // Everything here lands in auth.users.raw_user_meta_data, which the
          // handle_new_user trigger reads. The trigger is SECURITY DEFINER, so
          // it can write profiles even when the caller has no session yet.
          //
          // `username` MUST travel this way. The profile upsert further down
          // cannot set it on the email-verification path: RLS on profiles
          // requires auth.uid() = id for INSERT/UPDATE, and signUp() returns a
          // user with NO session, so auth.uid() is NULL and the write is
          // rejected. That failure was only console.warn'd (and warn is
          // stripped in TestFlight), so it went unnoticed -- 0 of 23 profiles
          // had a username, and every social surface showed "Unknown".
          //
          // referral_code: omitted entirely when blank so an untouched field
          // can never be mistaken for an attributed signup.
          data: {
            ...(trimmedUsername ? { username: trimmedUsername } : {}),
            ...(trimmedReferralCode ? { referral_code: trimmedReferralCode } : {}),
          },
        },
      });
      if (error) throw error;

      const user = data.user;
      if (!user) {
        showToast({ message: t('auth.errors.sign_up_no_user'), type: 'error' });
        return;
      }

      // Supabase silently fakes a "successful" signUp when the email is already
      // registered (security: doesn't leak whether an email exists). The tell:
      // identities is an empty array. Without this guard, the user is routed to
      // verify-email and waits forever for an email that never arrives.
      if (Array.isArray(user.identities) && user.identities.length === 0) {
        showToast({
          message: t('auth.errors.email_already_registered'),
          type: 'warning',
        });
        router.replace('/(auth)/login');
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
         
        console.warn('[register] profile upsert failed', code, profileError);
      }

      if (trimmedReferralCode) void clearPendingReferralCode();

      track({
        name: 'user_signed_up',
        properties: {
          method: 'email',
          ...(trimmedReferralCode ? { affiliate_code: trimmedReferralCode } : {}),
        },
      });

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
                  testID="username-input"
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
                  testID="email-input"
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
                  testID="password-input"
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

              <Animated.View style={[{ marginTop: 14 }, getItemStyle(4)]}>
                {/* Creator code — optional. This is the only point at which a
                    creator's attribution enters the system: it rides along on
                    signUp() metadata into auth.users.raw_user_meta_data, and the
                    handle_new_user trigger copies it to profiles.referred_by_code. */}
                <AuthTextInput
                  testID="referral-code-input"
                  label={codeFromLink ? "Creator code (from your link)" : "Creator code (optional)"}
                  icon="pricetag-outline"
                  value={referralCode}
                  onChangeText={setReferralCode}
                  autoCapitalize="characters"
                  autoCorrect={false}
                  returnKeyType="done"
                  onSubmitEditing={handleSignUp}
                />
              </Animated.View>

              <Animated.View style={getItemStyle(5)}>
                {/* Animated Terms checkbox — above the button so users agree before acting */}
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
              </Animated.View>
            </View>

            {/* Footer */}
            <Animated.View style={getItemStyle(6)}>
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
