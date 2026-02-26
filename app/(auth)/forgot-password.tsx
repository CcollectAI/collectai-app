/**
 * Forgot Password screen — sends password reset email via Supabase.
 */

import React, { useEffect, useState } from 'react';
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
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
const INPUT_BG = '#F8FAFC';

function ForgotPasswordScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function handleReset() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      showToast({ message: 'Enter your email address to reset your password.', type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(trimmedEmail, {
        redirectTo: 'collectai://reset-password',
      });
      if (error) throw error;
      setSent(true);
      setCooldown(60);
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Reset failed. Unknown error.', type: 'error' });
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
          {/* Back button */}
          <AnimatedPressable
            style={styles.backBtn}
            onPress={() => router.back()}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="arrow-back" size={24} color={NAVY} />
          </AnimatedPressable>

          {/* Brand */}
          <View style={styles.brandSection}>
            <View style={styles.iconCircle}>
              <Ionicons name="key-outline" size={32} color={TIFFANY_DARK} />
            </View>
            <Text style={styles.brandTitle}>Reset Password</Text>
            <Text style={styles.brandSubtitle}>
              {sent
                ? 'Check your inbox for a reset link'
                : "Enter your email and we'll send you a reset link"}
            </Text>
          </View>

          {sent ? (
            <View style={styles.successSection}>
              <View style={styles.successIcon}>
                <Ionicons name="checkmark-circle" size={48} color={TIFFANY} />
              </View>
              <Text style={styles.successText}>
                We sent a password reset link to{'\n'}
                <Text style={{ fontWeight: '700' }}>{email.trim()}</Text>
              </Text>
              <Text style={styles.successHint}>
                Didn't receive it? Check your spam folder or try again.
              </Text>

              <AnimatedPressable
                style={[styles.primaryBtn, cooldown > 0 && { opacity: 0.6 }]}
                onPress={() => {
                  if (cooldown > 0) return;
                  setSent(false);
                  setEmail('');
                }}
                disabled={cooldown > 0}
                accessibilityRole="button"
                accessibilityLabel={cooldown > 0 ? `Try again in ${cooldown} seconds` : 'Try again'}
              >
                <Text style={styles.primaryBtnText}>
                  {cooldown > 0 ? `Try Again (${cooldown}s)` : 'Try Again'}
                </Text>
              </AnimatedPressable>

              <AnimatedPressable
                style={styles.secondaryBtn}
                onPress={() => router.replace('/(auth)/login')}
                accessibilityRole="button"
                accessibilityLabel="Back to sign in"
              >
                <Text style={styles.secondaryBtnText}>Back to Sign In</Text>
              </AnimatedPressable>
            </View>
          ) : (
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
                returnKeyType="send"
                onSubmitEditing={handleReset}
              />

              {loading ? (
                <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 24 }} />
              ) : (
                <AnimatedPressable
                  style={styles.primaryBtn}
                  onPress={handleReset}
                  accessibilityRole="button"
                  accessibilityLabel="Send reset link"
                >
                  <Text style={styles.primaryBtnText}>Send Reset Link</Text>
                </AnimatedPressable>
              )}

              <AnimatedPressable
                style={styles.footer}
                onPress={() => router.back()}
                accessibilityRole="link"
                accessibilityLabel="Back to sign in"
              >
                <Text style={styles.footerText}>
                  Remember your password?{' '}
                  <Text style={styles.footerLink}>Sign in</Text>
                </Text>
              </AnimatedPressable>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
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
    backgroundColor: '#FFFFFF',
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
    backgroundColor: TIFFANY + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  brandTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: NAVY,
  },
  brandSubtitle: {
    fontSize: 15,
    color: MUTED,
    marginTop: 8,
    textAlign: 'center',
    lineHeight: 22,
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
  primaryBtn: {
    backgroundColor: TIFFANY,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    alignSelf: 'stretch',
    marginTop: 24,
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryBtn: {
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    alignSelf: 'stretch',
    marginTop: 12,
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: '600',
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
  successSection: {
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  successIcon: {
    marginBottom: 16,
  },
  successText: {
    fontSize: 16,
    color: NAVY,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 8,
  },
  successHint: {
    fontSize: 13,
    color: MUTED,
    textAlign: 'center',
    marginBottom: 32,
  },
});
