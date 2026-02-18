/**
 * Register screen — username + email + password sign-up.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Alert,
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

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
const INPUT_BG = '#F8FAFC';

export default function RegisterScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSignUp() {
    const trimmedUsername = username.trim();
    const trimmedEmail = email.trim();

    if (!trimmedUsername || !trimmedEmail || !password) {
      Alert.alert('Missing fields', 'Please fill in all fields.');
      return;
    }

    if (password.length < 6) {
      Alert.alert('Weak password', 'Password must be at least 6 characters.');
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
          Alert.alert('Username taken', 'Please choose another username.');
          return;
        }
        throw profileError;
      }

      // Success — onAuthStateChange will fire, AuthProvider picks up the session.
      // Root layout will redirect to onboarding since it's a new user.
      router.replace('/(auth)/onboarding');
    } catch (e: unknown) {
      Alert.alert('Sign up failed', e instanceof Error ? e.message : 'Unknown error');
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
            />

            <Text style={[styles.label, { marginTop: 16 }]}>Email</Text>
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
            />

            <Text style={[styles.label, { marginTop: 16 }]}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="At least 6 characters"
              placeholderTextColor={MUTED}
              secureTextEntry
              autoComplete="new-password"
              accessibilityLabel="Password"
            />

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

          {/* Legal links */}
          <Text style={styles.legalText}>
            By creating an account, you agree to our{' '}
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
            .
          </Text>

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
  legalText: {
    fontSize: 13,
    color: MUTED,
    textAlign: 'center',
    lineHeight: 20,
    marginTop: 16,
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
