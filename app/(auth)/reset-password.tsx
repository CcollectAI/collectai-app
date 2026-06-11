/**
 * Reset Password screen — where the password-recovery deep link lands.
 *
 * Flow: forgot-password sends resetPasswordForEmail(redirectTo: sparrow://reset-password).
 * The email link verifies (type=recovery) and reopens the app with the session in
 * the URL fragment; AuthProvider's deep-link handler calls setSession and routes
 * here. The user sets a new password via supabase.auth.updateUser.
 *
 * Created 2026-06-11 — this route previously did not exist, so the recovery link
 * fell through to the login screen (reported as "reset just pushes you to login").
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { AuthTextInput } from '@/components/auth/AuthTextInput';
import { useAuthContext } from '@/providers/useAuthContext';
import { setRecoveryPending } from '@/auth/recoveryState';
import { fonts } from '@/theme/tokens';

function ResetPasswordScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { user, loading: authLoading } = useAuthContext();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  // The recovery session is set by AuthProvider before routing here. If there's
  // no session, the link was invalid/expired or this screen was opened directly.
  const noSession = !authLoading && !user;

  // Clear the recovery flag on the way out (success -> tabs, request-new-link,
  // or back-to-sign-in all unmount this screen) so the gate resumes normal routing.
  useEffect(() => {
    return () => setRecoveryPending(false);
  }, []);

  async function handleUpdate() {
    if (password.length < 8) {
      showToast({ message: 'Password must be at least 8 characters.', type: 'warning' });
      return;
    }
    if (password !== confirm) {
      showToast({ message: 'Passwords do not match.', type: 'warning' });
      return;
    }
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: "Password updated — you're all set.", type: 'success' });
      router.replace('/(tabs)');
    } catch (e: unknown) {
      showToast({
        message: e instanceof Error ? e.message : 'Could not update password. Please try again.',
        type: 'error',
      });
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
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
            <View style={styles.brandSection}>
              <View style={[styles.iconCircle, { backgroundColor: colors.brand.base + '20' }]}>
                <Ionicons name="lock-closed-outline" size={32} color={colors.brand.dark} />
              </View>
              <Text style={[styles.brandTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                Set a new password
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>
                {noSession
                  ? 'This reset link is invalid or has expired. Request a new one to continue.'
                  : 'Choose a new password for your Sparrow Collect account.'}
              </Text>
            </View>

            {noSession ? (
              <AnimatedPressable
                style={styles.gradientBtnWrap}
                onPress={() => router.replace('/(auth)/forgot-password')}
                accessibilityRole="button"
                accessibilityLabel="Request a new reset link"
              >
                <LinearGradient
                  colors={[colors.brand.dark, colors.brand.base]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={styles.gradientBtn}
                >
                  <Text style={styles.gradientBtnText}>Request a new link</Text>
                </LinearGradient>
              </AnimatedPressable>
            ) : (
              <View style={styles.form}>
                <AuthTextInput
                  label="New password"
                  icon="lock-closed-outline"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  autoCapitalize="none"
                  autoFocus
                  returnKeyType="next"
                />
                <View style={{ height: 12 }} />
                <AuthTextInput
                  label="Confirm new password"
                  icon="lock-closed-outline"
                  value={confirm}
                  onChangeText={setConfirm}
                  secureTextEntry
                  autoCapitalize="none"
                  returnKeyType="done"
                  onSubmitEditing={handleUpdate}
                />

                <AnimatedPressable
                  style={styles.gradientBtnWrap}
                  onPress={handleUpdate}
                  disabled={loading}
                  accessibilityRole="button"
                  accessibilityLabel="Update password"
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
                      <Text style={styles.gradientBtnText}>Update password</Text>
                    )}
                  </LinearGradient>
                </AnimatedPressable>
              </View>
            )}

            <AnimatedPressable
              style={styles.footer}
              onPress={() => router.replace('/(auth)/login')}
              accessibilityRole="link"
              accessibilityLabel="Back to sign in"
            >
              <Text style={[styles.footerText, { color: colors.brand.dark }]}>Back to sign in</Text>
            </AnimatedPressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function ResetPasswordScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Reset Password">
      <ResetPasswordScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flexGrow: 1, paddingHorizontal: 24, paddingVertical: 40, justifyContent: 'center' },
  brandSection: { alignItems: 'center', marginBottom: 40 },
  iconCircle: {
    width: 72, height: 72, borderRadius: 36,
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  brandTitle: { fontSize: 28, fontWeight: '800' },
  brandSubtitle: { fontSize: 15, marginTop: 8, textAlign: 'center', lineHeight: 22 },
  form: { marginBottom: 16 },
  gradientBtnWrap: {
    marginTop: 24, borderRadius: 16,
    shadowColor: '#44A9A1', shadowOpacity: 0.3, shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 }, elevation: 6, alignSelf: 'stretch',
  },
  gradientBtn: {
    borderRadius: 16, paddingVertical: 16,
    alignItems: 'center', justifyContent: 'center', minHeight: 54,
  },
  gradientBtnText: { color: '#FFFFFF', fontSize: 16, fontFamily: fonts.bold },
  footer: { alignItems: 'center', paddingVertical: 16, marginTop: 8 },
  footerText: { fontSize: 14, fontWeight: '600' },
});
