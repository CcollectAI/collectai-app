/**
 * The second step of sign-in for a member with 2FA (2026-09-24).
 *
 * Reached only from the root gate (app/_layout.tsx) when the session is aal1
 * and could be aal2 (src/auth/mfaGate.ts). Before this screen existed, 2FA was
 * enrolled and never asked for. On success the session becomes aal2 and the
 * gate lets the member through; "Sign out" is the way back for someone
 * without their authenticator.
 */
import React, { useState } from 'react';
import { View, Text, ActivityIndicator, KeyboardAvoidingView, ScrollView, StyleSheet, Keyboard } from 'react-native';
import { KEYBOARD_AVOIDING_BEHAVIOR } from '@/lib/keyboardAvoiding';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useTranslation } from 'react-i18next';
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
import { fonts } from '@/theme/tokens';
import { logger } from '@/lib/logger';

function MfaChallengeScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { signOut } = useAuthContext();
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);

  async function handleVerify() {
    Keyboard.dismiss();
    if (code.length !== 6) {
      showToast({ message: t('mfa_challenge.code_required'), type: 'warning' });
      return;
    }
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setVerifying(true);
    try {
      const { data: factors, error: listError } = await supabase.auth.mfa.listFactors();
      if (listError) throw listError;
      const factor = (factors?.totp ?? []).find((f) => f.status === 'verified');
      if (!factor) {
        // No verified factor: nothing is owed. Let the gate re-decide.
        router.replace('/(tabs)');
        return;
      }
      const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: factor.id, code });
      if (error) throw error;
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      router.replace('/(tabs)');
    } catch (e: unknown) {
      logger.error('[mfa-challenge] verify failed:', e);
      setCode('');
      showToast({ message: t('mfa_challenge.code_rejected'), type: 'error' });
    } finally {
      setVerifying(false);
    }
  }

  return (
    <GradientBackground>
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={KEYBOARD_AVOIDING_BEHAVIOR}>
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
            <View style={styles.brandSection}>
              <View style={[styles.iconCircle, { backgroundColor: colors.brand.base + '20' }]}>
                <Ionicons name="shield-checkmark-outline" size={32} color={colors.brand.dark} />
              </View>
              <Text style={[styles.brandTitle, { color: colors.text, fontFamily: fonts.bold }]}>
                {t('mfa_challenge.title')}
              </Text>
              <Text style={[styles.brandSubtitle, { color: colors.muted }]}>{t('mfa_challenge.body')}</Text>
            </View>

            <AuthTextInput
              label={t('mfa_challenge.code_label')}
              icon="keypad-outline"
              value={code}
              onChangeText={(v: string) => setCode(v.replace(/[^0-9]/g, '').slice(0, 6))}
              keyboardType="number-pad"
              autoComplete="one-time-code"
              autoCorrect={false}
              returnKeyType="done"
              onSubmitEditing={handleVerify}
            />

            <AnimatedPressable
              style={styles.gradientBtnWrap}
              onPress={handleVerify}
              disabled={verifying}
              accessibilityRole="button"
              accessibilityLabel={t('mfa_challenge.verify')}
            >
              <LinearGradient
                colors={[colors.brand.dark, colors.brand.base]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.gradientBtn}
              >
                {verifying ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.gradientBtnText}>{t('mfa_challenge.verify')}</Text>
                )}
              </LinearGradient>
            </AnimatedPressable>

            <AnimatedPressable
              style={styles.footer}
              onPress={() => { void signOut(); }}
              accessibilityRole="button"
              accessibilityLabel={t('account.sign_out')}
            >
              <Text style={[styles.footerText, { color: colors.brand.dark }]}>{t('account.sign_out')}</Text>
            </AnimatedPressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GradientBackground>
  );
}

export default function MfaChallengeScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="MFA Challenge">
      <MfaChallengeScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flexGrow: 1, paddingHorizontal: 24, paddingVertical: 40, justifyContent: 'center' },
  brandSection: { alignItems: 'center', marginBottom: 32 },
  iconCircle: {
    width: 72, height: 72, borderRadius: 36,
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  brandTitle: { fontSize: 28, fontWeight: '800', textAlign: 'center' },
  brandSubtitle: { fontSize: 15, marginTop: 8, textAlign: 'center', lineHeight: 22 },
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
