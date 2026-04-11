/**
 * Login screen — email/password sign-in with magic link, Apple, and Google options.
 * Pro-grade: gradient bg, floating-label inputs, stagger reveal, gradient button.
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
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '@/lib/supabase';
import { useAuthContext } from '@/providers/useAuthContext';
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

WebBrowser.maybeCompleteAuthSession();

const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
const GOOGLE_IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
const GOOGLE_ANDROID_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID;

function LoginScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const { colors, isDark } = useAppTheme();
  const { showToast } = useToast();
  const { signInDemo } = useAuthContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  const { getItemStyle } = useStaggerReveal({ count: 7, staggerMs: 60, fromY: 16 });

  useEffect(() => {
    if (Platform.OS === 'ios') {
      AppleAuthentication.isAvailableAsync().then(setAppleAvailable).catch(() => {});
    }
  }, []);

  const googleEnabled = !!(GOOGLE_WEB_CLIENT_ID || GOOGLE_IOS_CLIENT_ID || GOOGLE_ANDROID_CLIENT_ID);
  const [googleRequest, googleResponse, googlePromptAsync] = Google.useIdTokenAuthRequest(
    googleEnabled
      ? {
          clientId: GOOGLE_WEB_CLIENT_ID ?? undefined,
          iosClientId: GOOGLE_IOS_CLIENT_ID ?? undefined,
          androidClientId: GOOGLE_ANDROID_CLIENT_ID ?? undefined,
        }
      : { clientId: 'placeholder' },
  );

  useEffect(() => {
    if (googleResponse?.type === 'success') {
      const { id_token } = googleResponse.params;
      if (id_token) {
        setLoading(true);
        supabase.auth
          .signInWithIdToken({ provider: 'google', token: id_token })
          .then(({ error }) => {
            if (error) throw error;
            track({ name: 'user_logged_in', properties: { method: 'google' } });
            router.replace('/(tabs)');
          })
          .catch((e: unknown) => {
            showToast({ message: e instanceof Error ? e.message : t('auth.errors.google_sign_in_failed'), type: 'error' });
          })
          .finally(() => setLoading(false));
      }
    }
  }, [googleResponse]);

  async function handleAppleSignIn() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (!credential.identityToken) {
        showToast({ message: t('auth.errors.no_identity_token'), type: 'error' });
        return;
      }
      setLoading(true);
      const { error } = await supabase.auth.signInWithIdToken({
        provider: 'apple',
        token: credential.identityToken,
      });
      if (error) throw error;
      track({ name: 'user_logged_in', properties: { method: 'apple' } });
      router.replace('/(tabs)');
    } catch (e: unknown) {
      const code = (e as { code?: string })?.code;
      if (code === 'ERR_REQUEST_CANCELED') return;
      showToast({ message: e instanceof Error ? e.message : t('auth.errors.apple_sign_in_failed'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  function handleDemoLogin() {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    AsyncStorage.setItem('@collectai/onboarding_complete', 'true').catch(() => {});
    signInDemo();
    track({ name: 'user_logged_in', properties: { method: 'demo' } });
    router.replace('/(tabs)');
  }

  async function handleSignIn() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      showToast({ message: t('auth.errors.email_password_required'), type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: trimmedEmail,
        password,
      });
      if (error) throw error;
      track({ name: 'user_logged_in', properties: { method: 'email' } });
      router.replace('/(tabs)');
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : t('auth.errors.sign_in_failed'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleMagicLink() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      showToast({ message: t('auth.errors.magic_link_email_required'), type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: trimmedEmail,
        options: { shouldCreateUser: false },
      });
      if (error) throw error;
      showToast({ message: 'We sent you a magic sign-in link. Check your email.', type: 'success' });
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : t('auth.errors.magic_link_failed'), type: 'error' });
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
            {/* Brand */}
            <Animated.View style={[styles.brandSection, getItemStyle(0)]}>
              <View style={[styles.iconCircleOuter, { backgroundColor: colors.brand.base + '15' }]}>
                {Platform.OS === 'ios' ? (
                  <BlurView intensity={40} tint={isDark ? 'dark' : 'light'} style={styles.iconCircle}>
                    <Image source={require('../../assets/images/logo.png')} style={{ width: 68, height: 68 }} resizeMode="contain" />
                  </BlurView>
                ) : (
                  <View style={[styles.iconCircle, { backgroundColor: colors.brand.base + '25' }]}>
                    <Image source={require('../../assets/images/logo.png')} style={{ width: 68, height: 68 }} resizeMode="contain" />
                  </View>
                )}
              </View>
              <Text style={[styles.brandTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                CollectAI
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>{t('auth.welcome_back')}</Text>
            </Animated.View>

            {/* Form */}
            <View style={styles.form}>
              <Animated.View style={getItemStyle(1)}>
                <AuthTextInput
                  label="Email"
                  icon="mail-outline"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoComplete="email"
                  autoCapitalize="none"
                  autoFocus
                  returnKeyType="next"
                  onSubmitEditing={() => passwordRef.current?.focus()}
                  testID="email-input"
                />
              </Animated.View>

              <Animated.View style={[{ marginTop: 14 }, getItemStyle(2)]}>
                <AuthTextInput
                  ref={passwordRef}
                  label="Password"
                  icon="lock-closed-outline"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  autoComplete="password"
                  returnKeyType="go"
                  onSubmitEditing={handleSignIn}
                  testID="password-input"
                />
              </Animated.View>

              <Animated.View style={getItemStyle(3)}>
                <AnimatedPressable
                  style={styles.gradientBtnWrap}
                  onPress={handleSignIn}
                  disabled={loading}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.sign_in')}
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
                      <Text style={styles.gradientBtnText}>{t('auth.login.sign_in_button')}</Text>
                    )}
                  </LinearGradient>
                </AnimatedPressable>

                <View style={styles.linksRow}>
                  <AnimatedPressable
                    onPress={() => router.push('/(auth)/forgot-password')}
                    accessibilityRole="link"
                    accessibilityLabel={t('auth.forgot_password')}
                  >
                    <Text style={[styles.linkText, { color: colors.brand.dark }]}>{t('auth.forgot_password')}</Text>
                  </AnimatedPressable>

                  <AnimatedPressable
                    onPress={handleMagicLink}
                    accessibilityRole="button"
                    accessibilityLabel={t('auth.magic_link')}
                  >
                    <View style={styles.magicLinkRow}>
                      <Ionicons name="mail-outline" size={15} color={colors.brand.dark} />
                      <Text style={[styles.linkText, { color: colors.brand.dark }]}>{t('auth.magic_link')}</Text>
                    </View>
                  </AnimatedPressable>
                </View>
              </Animated.View>
            </View>

            {/* Divider */}
            <Animated.View style={[styles.dividerRow, getItemStyle(4)]}>
              <LinearGradient
                colors={['transparent', colors.border, 'transparent']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.dividerGradient}
              />
              <Text style={[styles.dividerText, { color: colors.muted }]}>or</Text>
              <LinearGradient
                colors={['transparent', colors.border, 'transparent']}
                start={{ x: 1, y: 0 }}
                end={{ x: 0, y: 0 }}
                style={styles.dividerGradient}
              />
            </Animated.View>

            {/* Social Login */}
            <Animated.View style={getItemStyle(5)}>
              {appleAvailable && (
                <AnimatedPressable
                  style={[styles.socialBtn, { backgroundColor: isDark ? '#FFFFFF' : '#000000' }]}
                  onPress={handleAppleSignIn}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.continue_with_apple')}
                >
                  <Ionicons name="logo-apple" size={20} color={isDark ? '#000000' : '#FFFFFF'} />
                  <Text style={[styles.socialBtnText, { color: isDark ? '#000000' : '#FFFFFF' }]}>
                    {t('auth.continue_with_apple')}
                  </Text>
                </AnimatedPressable>
              )}

              {googleEnabled && (
                <AnimatedPressable
                  style={[
                    styles.socialBtn,
                    {
                      backgroundColor: colors.background,
                      borderWidth: 1.5,
                      borderColor: colors.border,
                      marginTop: appleAvailable ? 10 : 0,
                    },
                  ]}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    googlePromptAsync();
                  }}
                  disabled={!googleRequest}
                  accessibilityRole="button"
                  accessibilityLabel={t('auth.continue_with_google')}
                >
                  <Text style={{ fontSize: 18, fontWeight: '700', color: '#4285F4' }}>G</Text>
                  <Text style={[styles.socialBtnText, { color: colors.text }]}>
                    {t('auth.continue_with_google')}
                  </Text>
                </AnimatedPressable>
              )}

              {/* Demo Login */}
              <AnimatedPressable
                style={[
                  styles.demoBtn,
                  {
                    borderColor: colors.brand.base,
                    backgroundColor: colors.brand.base + '10',
                    marginTop: (appleAvailable || googleEnabled) ? 16 : 0,
                  },
                ]}
                onPress={handleDemoLogin}
                accessibilityRole="button"
                accessibilityLabel={t('auth.try_demo_mode')}
              >
                <Ionicons name="play-circle-outline" size={20} color={colors.brand.dark} />
                <Text style={[styles.demoBtnText, { color: colors.brand.dark }]}>{t('auth.try_demo_mode')}</Text>
              </AnimatedPressable>
            </Animated.View>

            {/* Footer */}
            <Animated.View style={getItemStyle(6)}>
              <AnimatedPressable
                style={styles.footer}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push('/(auth)/register');
                }}
                accessibilityRole="link"
                accessibilityLabel={t('auth.create_account')}
              >
                <Text style={[styles.footerText, { color: colors.muted }]}>
                  {t('auth.no_account')}{' '}
                  <Text style={{ color: colors.brand.dark, fontWeight: '600' }}>{t('auth.sign_up')}</Text>
                </Text>
              </AnimatedPressable>
            </Animated.View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function LoginScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Login">
      <LoginScreen />
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
  linksRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 14,
    paddingHorizontal: 4,
  },
  magicLinkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  linkText: {
    fontSize: 13,
    fontWeight: '600',
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  dividerGradient: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    fontSize: 13,
    fontWeight: '500',
  },
  socialBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 14,
    borderRadius: 16,
    minHeight: 54,
  },
  socialBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  demoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderWidth: 2,
    borderRadius: 16,
    marginBottom: 8,
  },
  demoBtnText: {
    fontSize: 15,
    fontWeight: '700',
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  footerText: {
    fontSize: 14,
  },
});
