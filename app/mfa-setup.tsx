/**
 * MFA Setup screen — enroll/unenroll TOTP two-factor authentication.
 *
 * Uses Supabase Auth MFA SDK:
 * - supabase.auth.mfa.enroll() — returns QR code URI
 * - supabase.auth.mfa.verify() — verify TOTP code after scanning
 * - supabase.auth.mfa.unenroll() — remove factor
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  ActivityIndicator,
  Alert,
  StyleSheet,
  ScrollView,
  Image,
} from 'react-native';
// SafeAreaView removed — Stack header handles safe area
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '@/lib/supabase';
import { AnimatedPressable } from '@/motion';
import { useToast } from '@/components/Toast';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { QuickNavBar } from '@/components/QuickNavBar';
import { useAppTheme } from '@/hooks/useAppTheme';

type MFAFactor = {
  id: string;
  friendly_name?: string;
  factor_type: string;
  status: string;
};

function MFASetupScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { colors } = useAppTheme();
  const TIFFANY = colors.brand.base;
  const NAVY = colors.text;
  const MUTED = colors.muted;
  const BORDER = colors.border;
  const SUCCESS = colors.success;
  const DANGER = colors.danger;
  const INPUT_BG = colors.card;
  const [loading, setLoading] = useState(true);
  const [factors, setFactors] = useState<MFAFactor[]>([]);
  const [enrolling, setEnrolling] = useState(false);
  const [qrUri, setQrUri] = useState<string | null>(null);
  const [factorId, setFactorId] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    loadFactors();
  }, []);

  async function loadFactors() {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.mfa.listFactors();
      if (error) throw error;
      setFactors(data?.totp ?? []);
    } catch {
      // MFA not available or error
    } finally {
      setLoading(false);
    }
  }

  const hasVerifiedFactor = factors.some((f) => f.status === 'verified');

  async function handleEnroll() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setEnrolling(true);
    try {
      const { data, error } = await supabase.auth.mfa.enroll({
        factorType: 'totp',
        friendlyName: 'CollectAI Authenticator',
      });
      if (error) throw error;
      setQrUri(data.totp.qr_code);
      setFactorId(data.id);
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Failed to start MFA enrollment.', type: 'error' });
    } finally {
      setEnrolling(false);
    }
  }

  async function handleVerify() {
    if (!factorId || totpCode.length !== 6) {
      showToast({ message: 'Please enter the 6-digit code from your authenticator app.', type: 'warning' });
      return;
    }

    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setVerifying(true);
    try {
      const { data: challengeData, error: challengeError } = await supabase.auth.mfa.challenge({
        factorId,
      });
      if (challengeError) throw challengeError;

      const { error: verifyError } = await supabase.auth.mfa.verify({
        factorId,
        challengeId: challengeData.id,
        code: totpCode,
      });
      if (verifyError) throw verifyError;

      showToast({ message: 'Two-factor authentication has been enabled.', type: 'success' });
      setQrUri(null);
      setFactorId(null);
      setTotpCode('');
      await loadFactors();
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Invalid code. Please try again.', type: 'error' });
    } finally {
      setVerifying(false);
    }
  }

  async function handleUnenroll(fId: string) {
    Alert.alert(
      'Disable 2FA',
      'Are you sure you want to disable two-factor authentication? This makes your account less secure.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disable',
          style: 'destructive',
          onPress: async () => {
            try {
              const { error } = await supabase.auth.mfa.unenroll({ factorId: fId });
              if (error) throw error;
              showToast({ message: 'Two-factor authentication has been removed.', type: 'success' });
              await loadFactors();
            } catch (e: unknown) {
              showToast({ message: e instanceof Error ? e.message : 'Failed to disable 2FA.', type: 'error' });
            }
          },
        },
      ],
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: NAVY }]}>Two-Factor Authentication</Text>
        <Text style={[styles.subtitle, { color: MUTED }]}>
          Add an extra layer of security to your account with TOTP authenticator app.
        </Text>

        {loading ? (
          <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 40 }} />
        ) : qrUri ? (
          /* Enrollment flow: show QR + code entry */
          <View style={styles.enrollSection}>
            <Text style={[styles.stepTitle, { color: NAVY }]}>1. Scan this QR code</Text>
            <Text style={[styles.stepDesc, { color: MUTED }]}>
              Open your authenticator app (Google Authenticator, Authy, etc.) and scan this code:
            </Text>
            <View style={[styles.qrContainer, { borderColor: BORDER }]}>
              <Image
                source={{ uri: qrUri }}
                style={styles.qrImage}
                accessibilityLabel="QR code for authenticator app"
              />
            </View>

            <Text style={[styles.stepTitle, { color: NAVY, marginTop: 24 }]}>2. Enter the 6-digit code</Text>
            <TextInput
              style={[styles.codeInput, { backgroundColor: INPUT_BG, borderColor: BORDER, color: NAVY }]}
              value={totpCode}
              onChangeText={(t) => setTotpCode(t.replace(/[^0-9]/g, ''))}
              placeholder="000000"
              placeholderTextColor={MUTED}
              keyboardType="number-pad"
              maxLength={6}
              autoFocus
              accessibilityLabel="TOTP verification code"
            />

            {verifying ? (
              <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 16 }} />
            ) : (
              <AnimatedPressable
                style={[styles.primaryBtn, { backgroundColor: TIFFANY }]}
                onPress={handleVerify}
                accessibilityRole="button"
                accessibilityLabel="Verify code"
              >
                <Text style={styles.primaryBtnText}>Verify & Enable</Text>
              </AnimatedPressable>
            )}

            <AnimatedPressable
              style={styles.cancelBtn}
              onPress={() => {
                setQrUri(null);
                setFactorId(null);
                setTotpCode('');
              }}
              accessibilityRole="button"
              accessibilityLabel="Cancel enrollment"
            >
              <Text style={[styles.cancelBtnText, { color: MUTED }]}>Cancel</Text>
            </AnimatedPressable>
          </View>
        ) : hasVerifiedFactor ? (
          /* Already enrolled */
          <View style={styles.statusSection}>
            <View style={styles.statusBadge}>
              <Ionicons name="shield-checkmark" size={32} color={SUCCESS} />
              <Text style={[styles.statusText, { color: SUCCESS }]}>2FA is enabled</Text>
            </View>
            <Text style={[styles.statusDesc, { color: MUTED }]}>
              Your account is protected with two-factor authentication.
            </Text>

            {factors
              .filter((f) => f.status === 'verified')
              .map((f) => (
                <View key={f.id} style={[styles.factorRow, { borderColor: BORDER }]}>
                  <View>
                    <Text style={[styles.factorName, { color: NAVY }]}>{f.friendly_name || 'Authenticator'}</Text>
                    <Text style={[styles.factorType, { color: MUTED }]}>TOTP</Text>
                  </View>
                  <AnimatedPressable
                    onPress={() => handleUnenroll(f.id)}
                    accessibilityRole="button"
                    accessibilityLabel="Remove this factor"
                  >
                    <Text style={[styles.removeText, { color: DANGER }]}>Remove</Text>
                  </AnimatedPressable>
                </View>
              ))}
          </View>
        ) : (
          /* Not enrolled — show enroll button */
          <View style={styles.statusSection}>
            <View style={styles.statusBadge}>
              <Ionicons name="shield-outline" size={32} color={MUTED} />
              <Text style={[styles.statusText, { color: MUTED }]}>2FA is not enabled</Text>
            </View>
            <Text style={[styles.statusDesc, { color: MUTED }]}>
              Protect your account by enabling two-factor authentication with an authenticator app.
            </Text>

            {enrolling ? (
              <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 24 }} />
            ) : (
              <AnimatedPressable
                style={[styles.primaryBtn, { backgroundColor: TIFFANY }]}
                onPress={handleEnroll}
                accessibilityRole="button"
                accessibilityLabel="Enable two-factor authentication"
              >
                <Ionicons name="shield-checkmark-outline" size={18} color="#FFF" />
                <Text style={styles.primaryBtnText}>Enable 2FA</Text>
              </AnimatedPressable>
            )}
          </View>
        )}
      </ScrollView>
      <QuickNavBar />
    </View>
  );
}

export default function MFASetupScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="MFA Setup">
      <MFASetupScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scroll: {
    paddingHorizontal: 24,
    paddingVertical: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 32,
  },
  statusSection: {
    alignItems: 'center',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  statusText: {
    fontSize: 18,
    fontWeight: '700',
  },
  statusDesc: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  factorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
  },
  factorName: {
    fontSize: 15,
    fontWeight: '600',
  },
  factorType: {
    fontSize: 12,
    marginTop: 2,
  },
  removeText: {
    fontSize: 14,
    fontWeight: '600',
  },
  enrollSection: {
    alignItems: 'center',
  },
  stepTitle: {
    fontSize: 16,
    fontWeight: '700',
    alignSelf: 'flex-start',
    marginBottom: 6,
  },
  stepDesc: {
    fontSize: 14,
    lineHeight: 22,
    alignSelf: 'flex-start',
    marginBottom: 16,
  },
  qrContainer: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  qrImage: {
    width: 200,
    height: 200,
  },
  codeInput: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 20,
    paddingVertical: 16,
    fontSize: 24,
    fontWeight: '700',
    letterSpacing: 8,
    textAlign: 'center',
    width: '100%',
    marginTop: 8,
  },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 16,
    width: '100%',
    marginTop: 24,
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  cancelBtn: {
    paddingVertical: 14,
    marginTop: 8,
  },
  cancelBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
