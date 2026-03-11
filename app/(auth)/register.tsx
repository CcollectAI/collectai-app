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
import { useAppTheme } from '@/hooks/useAppTheme';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { track } from '@/analytics/track';
import { GradientBackground } from '@/components/auth/GradientBackground';
import { AuthTextInput } from '@/components/auth/AuthTextInput';
import { fonts } from '@/theme/tokens';

function RegisterScreen() {
  const router = useRouter();
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

    if (score <= 1) return { label: 'Weak', percent: 20, color: '#EF4444' };
    if (score === 2) return { label: 'Fair', percent: 40, color: '#F59E0B' };
    if (score === 3) return { label: 'Good', percent: 60, color: '#F59E0B' };
    if (score === 4) return { label: 'Strong', percent: 80, color: '#22C55E' };
    return { label: 'Excellent', percent: 100, color: '#22C55E' };
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
        router.replace({
          pathname: '/(auth)/verify-email',
          params: { email: trimmedEmail },
        });
        return;
      }

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

      track({ name: 'user_signed_up', properties: { method: 'email' } });
      router.replace('/(auth)/onboarding');
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Sign up failed. Unknown error.', type: 'error' });
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
                Create Account
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>
                Join the collector community
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
                  accessibilityLabel="Create account"
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
                      <Text style={styles.gradientBtnText}>Create Account</Text>
                    )}
                  </LinearGradient>
                </AnimatedPressable>

                {/* Animated Terms checkbox */}
                <AnimatedPressable
                  style={styles.termsRow}
                  onPress={toggleTerms}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: termsAccepted }}
                  accessibilityLabel="Accept Terms of Service and Privacy Policy"
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
                    I agree to the{' '}
                    <Text
                      style={[styles.legalLink, { color: colors.brand.dark }]}
                      onPress={() => router.push('/legal/terms')}
                      accessibilityRole="link"
                    >
                      Terms of Service
                    </Text>
                    {' '}and{' '}
                    <Text
                      style={[styles.legalLink, { color: colors.brand.dark }]}
                      onPress={() => router.push('/legal/privacy-policy')}
                      accessibilityRole="link"
                    >
                      Privacy Policy
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
                accessibilityLabel="Sign in instead"
              >
                <Text style={[styles.footerText, { color: colors.muted }]}>
                  Already have an account?{' '}
                  <Text style={{ color: colors.brand.dark, fontWeight: '600' }}>Sign in</Text>
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
