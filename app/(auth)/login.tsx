/**
 * Login screen — email/password sign-in with magic link, Apple, and Google options.
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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '@/lib/supabase';
import { useAuthContext } from '@/providers/useAuthContext';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';

WebBrowser.maybeCompleteAuthSession();

const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
const GOOGLE_IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
const GOOGLE_ANDROID_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID;

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
const INPUT_BG = '#F8FAFC';

function LoginScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { signInDemo } = useAuthContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  // Check Apple Sign In availability (iOS only)
  useEffect(() => {
    if (Platform.OS === 'ios') {
      AppleAuthentication.isAvailableAsync().then(setAppleAvailable).catch(() => {});
    }
  }, []);

  // Google auth session
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

  // Handle Google sign-in response
  useEffect(() => {
    if (googleResponse?.type === 'success') {
      const { id_token } = googleResponse.params;
      if (id_token) {
        setLoading(true);
        supabase.auth
          .signInWithIdToken({ provider: 'google', token: id_token })
          .then(({ error }) => {
            if (error) throw error;
            router.replace('/(tabs)');
          })
          .catch((e: unknown) => {
            showToast({ message: e instanceof Error ? e.message : 'Google sign in failed', type: 'error' });
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
        showToast({ message: 'No identity token received.', type: 'error' });
        return;
      }
      setLoading(true);
      const { error } = await supabase.auth.signInWithIdToken({
        provider: 'apple',
        token: credential.identityToken,
      });
      if (error) throw error;
      router.replace('/(tabs)');
    } catch (e: unknown) {
      const code = (e as { code?: string })?.code;
      if (code === 'ERR_REQUEST_CANCELED') return; // user cancelled
      showToast({ message: e instanceof Error ? e.message : 'Apple sign in failed', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  function handleDemoLogin() {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    AsyncStorage.setItem('@collectai/onboarding_complete', 'true').catch(() => {});
    signInDemo();
    router.replace('/(tabs)');
  }

  async function handleSignIn() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      showToast({ message: 'Please enter your email and password.', type: 'warning' });
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
      // onAuthStateChange in AuthProvider handles the rest
      router.replace('/(tabs)');
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Sign in failed', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleMagicLink() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      showToast({ message: 'Enter your email to receive a magic link.', type: 'warning' });
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
      showToast({ message: e instanceof Error ? e.message : 'Magic link failed', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  return (
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
          <View style={styles.brandSection}>
            <View style={styles.iconCircle}>
              <Ionicons name="diamond-outline" size={36} color={TIFFANY_DARK} />
            </View>
            <Text style={styles.brandSubtitle}>Welcome back</Text>
          </View>

          {/* Form */}
          <View style={styles.form}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={MUTED}
              autoCapitalize="none"
              keyboardType="email-address"
              autoComplete="email"
              accessibilityLabel="Email"
              autoFocus
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
            />

            <Text style={[styles.label, { marginTop: 16 }]}>Password</Text>
            <TextInput
              ref={passwordRef}
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter your password"
              placeholderTextColor={MUTED}
              secureTextEntry
              autoComplete="password"
              accessibilityLabel="Password"
              returnKeyType="go"
              onSubmitEditing={handleSignIn}
            />

            {loading ? (
              <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 24 }} />
            ) : (
              <>
                <AnimatedPressable
                  style={styles.signInBtn}
                  onPress={handleSignIn}
                  accessibilityRole="button"
                  accessibilityLabel="Sign in"
                >
                  <Text style={styles.signInBtnText}>Sign In</Text>
                </AnimatedPressable>

                <AnimatedPressable
                  style={styles.forgotBtn}
                  onPress={() => router.push('/(auth)/forgot-password')}
                  accessibilityRole="link"
                  accessibilityLabel="Forgot password"
                >
                  <Text style={styles.forgotText}>Forgot password?</Text>
                </AnimatedPressable>

                <AnimatedPressable
                  style={styles.magicLinkBtn}
                  onPress={handleMagicLink}
                  accessibilityRole="button"
                  accessibilityLabel="Send magic link"
                >
                  <Ionicons name="mail-outline" size={18} color={TIFFANY_DARK} />
                  <Text style={styles.magicLinkText}>Email me a magic link</Text>
                </AnimatedPressable>
              </>
            )}
          </View>

          {/* Divider */}
          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
            <View style={styles.dividerLine} />
          </View>

          {/* Social Login */}
          {appleAvailable && (
            <AnimatedPressable
              style={styles.socialBtn}
              onPress={handleAppleSignIn}
              accessibilityRole="button"
              accessibilityLabel="Sign in with Apple"
            >
              <Ionicons name="logo-apple" size={20} color={NAVY} />
              <Text style={styles.socialBtnText}>Continue with Apple</Text>
            </AnimatedPressable>
          )}

          {googleEnabled && (
            <AnimatedPressable
              style={[styles.socialBtn, appleAvailable && { marginTop: 10 }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                googlePromptAsync();
              }}
              disabled={!googleRequest}
              accessibilityRole="button"
              accessibilityLabel="Sign in with Google"
            >
              <Ionicons name="logo-google" size={18} color="#4285F4" />
              <Text style={styles.socialBtnText}>Continue with Google</Text>
            </AnimatedPressable>
          )}

          {/* Demo Login */}
          <AnimatedPressable
            style={[styles.demoBtn, (appleAvailable || googleEnabled) && { marginTop: 16 }]}
            onPress={handleDemoLogin}
            accessibilityRole="button"
            accessibilityLabel="Try demo mode"
          >
            <Ionicons name="play-circle-outline" size={20} color={TIFFANY_DARK} />
            <Text style={styles.demoBtnText}>Try Demo Mode</Text>
          </AnimatedPressable>

          {/* Footer */}
          <AnimatedPressable
            style={styles.footer}
            onPress={() => router.push('/(auth)/register')}
            accessibilityRole="link"
            accessibilityLabel="Create an account"
          >
            <Text style={styles.footerText}>
              Don't have an account?{' '}
              <Text style={styles.footerLink}>Sign up</Text>
            </Text>
          </AnimatedPressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
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
    backgroundColor: '#FFFFFF',
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
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: TIFFANY + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  brandSubtitle: {
    fontSize: 16,
    color: MUTED,
    marginTop: 4,
  },
  form: {
    marginBottom: 32,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: NAVY,
    marginBottom: 6,
  },
  input: {
    backgroundColor: INPUT_BG,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 16,
    color: NAVY,
  },
  signInBtn: {
    backgroundColor: TIFFANY,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 24,
  },
  signInBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  forgotBtn: {
    alignSelf: 'flex-end',
    marginTop: 12,
  },
  forgotText: {
    fontSize: 13,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
  magicLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
  },
  magicLinkText: {
    fontSize: 14,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: BORDER,
  },
  dividerText: {
    fontSize: 13,
    color: MUTED,
    fontWeight: '500',
  },
  socialBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
  },
  socialBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: NAVY,
  },
  demoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderWidth: 2,
    borderColor: TIFFANY,
    borderRadius: 12,
    backgroundColor: TIFFANY + '10',
    marginBottom: 8,
  },
  demoBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: TIFFANY_DARK,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  footerText: {
    fontSize: 14,
    color: MUTED,
  },
  footerLink: {
    color: TIFFANY_DARK,
    fontWeight: '600',
  },
});
