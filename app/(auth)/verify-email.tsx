/**
 * Verify Email screen — shown after registration to guide users to check their inbox.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';

function VerifyEmailScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { email } = useLocalSearchParams<{ email: string }>();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  async function handleResend() {
    if (!email) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setResending(true);
    try {
      const { error } = await supabase.auth.resend({
        type: 'signup',
        email,
      });
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
      } catch {
        // Non-critical
      }
    }, 5000);

    // Stop polling after 5 minutes
    const timeout = setTimeout(() => clearInterval(interval), 300000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [router]);

  // Resend cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        {/* Icon */}
        <View style={styles.iconCircle}>
          <Ionicons name="mail-unread-outline" size={48} color={TIFFANY_DARK} />
        </View>

        {/* Title */}
        <Text style={styles.title}>Check your email</Text>

        {/* Description */}
        <Text style={styles.description}>
          We sent a confirmation link to{'\n'}
          <Text style={styles.emailText}>{email || 'your email'}</Text>
        </Text>

        <Text style={styles.hint}>
          Click the link in the email to verify your account, then come back here to sign in.
        </Text>

        {/* Resend */}
        {resending ? (
          <ActivityIndicator size="small" color={TIFFANY} style={{ marginTop: 32 }} />
        ) : cooldown > 0 ? (
          <View style={styles.cooldownBadge}>
            <Text style={styles.cooldownText}>Resend available in {cooldown}s</Text>
          </View>
        ) : resent ? (
          <AnimatedPressable
            style={styles.resendBtn}
            onPress={handleResend}
            accessibilityRole="button"
            accessibilityLabel="Resend verification email"
          >
            <Ionicons name="checkmark-circle" size={18} color={TIFFANY_DARK} />
            <Text style={styles.resendText}>Email sent — tap to resend</Text>
          </AnimatedPressable>
        ) : (
          <AnimatedPressable
            style={styles.resendBtn}
            onPress={handleResend}
            accessibilityRole="button"
            accessibilityLabel="Resend verification email"
          >
            <Text style={styles.resendText}>Resend email</Text>
          </AnimatedPressable>
        )}

        {/* Go to login */}
        <AnimatedPressable
          style={styles.primaryBtn}
          onPress={() => router.replace('/(auth)/login')}
          accessibilityRole="button"
          accessibilityLabel="Go to sign in"
        >
          <Text style={styles.primaryBtnText}>Go to Sign In</Text>
        </AnimatedPressable>

        {/* Skip verification */}
        <AnimatedPressable
          style={styles.skipBtn}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.replace('/(tabs)/add');
          }}
          accessibilityRole="button"
          accessibilityLabel="Skip email verification and continue to the app"
        >
          <Text style={styles.skipBtnText}>Skip for now</Text>
        </AnimatedPressable>

        {/* Spam hint */}
        <Text style={styles.spamHint}>
          Didn't receive the email? Check your spam folder.
        </Text>
      </View>
    </SafeAreaView>
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
    backgroundColor: '#FFFFFF',
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
    backgroundColor: TIFFANY + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: NAVY,
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    color: MUTED,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 8,
  },
  emailText: {
    fontWeight: '700',
    color: NAVY,
  },
  hint: {
    fontSize: 14,
    color: MUTED,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 8,
  },
  resendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 32,
    paddingVertical: 10,
    paddingHorizontal: 20,
  },
  cooldownBadge: {
    marginTop: 32,
    paddingVertical: 10,
    paddingHorizontal: 20,
  },
  cooldownText: {
    fontSize: 14,
    color: MUTED,
    fontWeight: '500',
  },
  resendText: {
    fontSize: 15,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
  resentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 32,
    paddingVertical: 10,
    paddingHorizontal: 20,
  },
  resentText: {
    fontSize: 15,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
  primaryBtn: {
    backgroundColor: TIFFANY,
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 48,
    alignItems: 'center',
    marginTop: 24,
    width: '100%',
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  skipBtn: {
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 32,
  },
  skipBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: MUTED,
    textDecorationLine: 'underline',
  },
  spamHint: {
    fontSize: 13,
    color: MUTED,
    textAlign: 'center',
    marginTop: 16,
  },
});
