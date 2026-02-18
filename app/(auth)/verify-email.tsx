/**
 * Verify Email screen — shown after registration to guide users to check their inbox.
 */

import React, { useState } from 'react';
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

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';

export default function VerifyEmailScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { email } = useLocalSearchParams<{ email: string }>();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

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
    } catch {
      // Silently fail — don't leak whether the email exists
    } finally {
      setResending(false);
    }
  }

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
        ) : resent ? (
          <View style={styles.resentBadge}>
            <Ionicons name="checkmark-circle" size={18} color={TIFFANY_DARK} />
            <Text style={styles.resentText}>Email resent</Text>
          </View>
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

        {/* Spam hint */}
        <Text style={styles.spamHint}>
          Didn't receive the email? Check your spam folder.
        </Text>
      </View>
    </SafeAreaView>
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
    marginTop: 32,
    paddingVertical: 10,
    paddingHorizontal: 20,
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
  spamHint: {
    fontSize: 13,
    color: MUTED,
    textAlign: 'center',
    marginTop: 16,
  },
});
