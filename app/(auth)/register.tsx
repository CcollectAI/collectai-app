/**
 * Register screen — username + email + password sign-up.
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
  TouchableOpacity,
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
import { track } from '@/analytics/track';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
const INPUT_BG = '#F8FAFC';

function RegisterScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  const getPasswordStrength = (pw: string): { label: string; percent: number; color: string } => {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;

    if (score <= 1) return { label: 'Weak', percent: 20, color: '#EF4444' };
    if (score === 2) return { label: 'Fair', percent: 40, color: '#F59E0B' };
    if (score === 3) return { label: 'Good', percent: 60, color: '#F59E0B' };
    if (score === 4) return { label: 'Strong', percent: 80, color: '#22C55E' };
    return { label: 'Excellent', percent: 100, color: '#22C55E' };
  };

  async function handleSignUp() {
    if (!termsAccepted) {
      showToast({ message: 'Please accept the Terms of Service and Privacy Policy.', type: 'warning' });
      return;
    }

    const trimmedUsername = username.trim();
    const trimmedEmail = email.trim();

    if (!trimmedUsername || !trimmedEmail || !password) {
      showToast({ message: 'Please fill in all fields.', type: 'warning' });
      return;
    }

    if (password.length < 8) {
      showToast({ message: 'Password must be at least 8 characters.', type: 'warning' });
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
      if (!user || !user.email_confirmed_at) {
        // Email confirmation required — redirect to verify screen
        router.replace({
          pathname: '/(auth)/verify-email',
          params: { email: trimmedEmail },
        });
        return;
      }

      // Insert profile row
      const { error: profileError } = await supabase.from('profiles').insert({
        id: user.id,
        username: trimmedUsername,
      });
      if (profileError) {
        const code = (profileError as { code?: string }).code;
        if (code === '23505') {
          showToast({ message: 'Username taken. Please choose another.', type: 'warning' });
          return;
        }
        throw profileError;
      }

      // Success — onAuthStateChange will fire, AuthProvider picks up the session.
      // Root layout will redirect to onboarding since it's a new user.
      track({ name: 'user_signed_up', properties: { method: 'email' } });
      router.replace('/(auth)/onboarding');
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Sign up failed. Unknown error.', type: 'error' });
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
              <Ionicons name="person-add-outline" size={32} color={TIFFANY_DARK} />
            </View>
            <Text style={styles.brandTitle}>Create Account</Text>
            <Text style={styles.brandSubtitle}>Join the collector community</Text>
          </View>

          {/* Form */}
          <View style={styles.form}>
            <Text style={styles.label}>Username</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              placeholder="yourname"
              placeholderTextColor={MUTED}
              autoCapitalize="none"
              autoComplete="username-new"
              accessibilityLabel="Username"
              autoFocus
              returnKeyType="next"
              onSubmitEditing={() => emailRef.current?.focus()}
            />

            <Text style={[styles.label, { marginTop: 16 }]}>Email</Text>
            <TextInput
              ref={emailRef}
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={MUTED}
              autoCapitalize="none"
              keyboardType="email-address"
              autoComplete="email"
              accessibilityLabel="Email"
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
            />

            <Text style={[styles.label, { marginTop: 16 }]}>Password</Text>
            <TextInput
              ref={passwordRef}
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="At least 8 characters"
              placeholderTextColor={MUTED}
              secureTextEntry
              autoComplete="new-password"
              accessibilityLabel="Password"
              returnKeyType="done"
              onSubmitEditing={handleSignUp}
            />

            {/* Password strength indicator */}
            {password.length > 0 && (
              <View style={styles.strengthContainer}>
                <View style={styles.strengthBarBg}>
                  <View
                    style={[
                      styles.strengthBarFill,
                      {
                        width: `${getPasswordStrength(password).percent}%`,
                        backgroundColor: getPasswordStrength(password).color,
                      },
                    ]}
                  />
                </View>
                <Text style={[styles.strengthLabel, { color: getPasswordStrength(password).color }]}>
                  {getPasswordStrength(password).label}
                </Text>
              </View>
            )}

            {loading ? (
              <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 24 }} />
            ) : (
              <AnimatedPressable
                style={styles.signUpBtn}
                onPress={handleSignUp}
                accessibilityRole="button"
                accessibilityLabel="Create account"
              >
                <Text style={styles.signUpBtnText}>Create Account</Text>
              </AnimatedPressable>
            )}
          </View>

          {/* Terms checkbox */}
          <AnimatedPressable
            style={styles.termsRow}
            onPress={() => setTermsAccepted(!termsAccepted)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: termsAccepted }}
            accessibilityLabel="Accept Terms of Service and Privacy Policy"
          >
            <View style={[styles.checkbox, termsAccepted && styles.checkboxChecked]}>
              {termsAccepted && <Ionicons name="checkmark" size={14} color="#FFFFFF" />}
            </View>
            <Text style={styles.termsText}>
              I agree to the{' '}
              <Text
                style={styles.legalLink}
                onPress={() => router.push('/legal/terms')}
                accessibilityRole="link"
              >
                Terms of Service
              </Text>
              {' '}and{' '}
              <Text
                style={styles.legalLink}
                onPress={() => router.push('/legal/privacy-policy')}
                accessibilityRole="link"
              >
                Privacy Policy
              </Text>
            </Text>
          </AnimatedPressable>

          {/* Footer */}
          <AnimatedPressable
            style={styles.footer}
            onPress={() => router.push('/(auth)/login')}
            accessibilityRole="link"
            accessibilityLabel="Sign in instead"
          >
            <Text style={styles.footerText}>
              Already have an account?{' '}
              <Text style={styles.footerLink}>Sign in</Text>
            </Text>
          </AnimatedPressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
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
  brandTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: NAVY,
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
  signUpBtn: {
    backgroundColor: TIFFANY,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 24,
  },
  signUpBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  termsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 16,
    paddingHorizontal: 4,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: BORDER,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  checkboxChecked: {
    backgroundColor: TIFFANY,
    borderColor: TIFFANY,
  },
  termsText: {
    flex: 1,
    fontSize: 13,
    color: MUTED,
    lineHeight: 20,
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
    backgroundColor: '#E2E8F0',
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
  legalLink: {
    color: TIFFANY_DARK,
    fontWeight: '600',
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
