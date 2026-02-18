/**
 * MFA Setup screen — enroll/unenroll TOTP two-factor authentication.
 *
 * Uses Supabase Auth MFA SDK:
 * - supabase.auth.mfa.enroll() — returns QR code URI
 * - supabase.auth.mfa.verify() — verify TOTP code after scanning
 * - supabase.auth.mfa.unenroll() — remove factor
 */

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
const SUCCESS = '#10B981';
const DANGER = '#EF4444';
const INPUT_BG = '#F8FAFC';

type MFAFactor = {
  id: string;
  friendly_name?: string;
  factor_type: string;
  status: string;
};

export default function MFASetupScreen() {
  const router = useRouter();
  const { settings } = useSettings();
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
      Alert.alert('Error', e instanceof Error ? e.message : 'Failed to start MFA enrollment.');
    } finally {
      setEnrolling(false);
    }
  }

  async function handleVerify() {
    if (!factorId || totpCode.length !== 6) {
      Alert.alert('Invalid code', 'Please enter the 6-digit code from your authenticator app.');
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

      Alert.alert('Success', 'Two-factor authentication has been enabled.');
      setQrUri(null);
      setFactorId(null);
      setTotpCode('');
      await loadFactors();
    } catch (e: unknown) {
      Alert.alert('Verification failed', e instanceof Error ? e.message : 'Invalid code. Please try again.');
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
              Alert.alert('Disabled', 'Two-factor authentication has been removed.');
              await loadFactors();
            } catch (e: unknown) {
              Alert.alert('Error', e instanceof Error ? e.message : 'Failed to disable 2FA.');
            }
          },
        },
      ],
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>Two-Factor Authentication</Text>
        <Text style={styles.subtitle}>
          Add an extra layer of security to your account with TOTP authenticator app.
        </Text>

        {loading ? (
          <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 40 }} />
        ) : qrUri ? (
          /* Enrollment flow: show QR + code entry */
          <View style={styles.enrollSection}>
            <Text style={styles.stepTitle}>1. Scan this QR code</Text>
            <Text style={styles.stepDesc}>
              Open your authenticator app (Google Authenticator, Authy, etc.) and scan this code:
            </Text>
            <View style={styles.qrContainer}>
              <Image
                source={{ uri: qrUri }}
                style={styles.qrImage}
                accessibilityLabel="QR code for authenticator app"
              />
            </View>

            <Text style={[styles.stepTitle, { marginTop: 24 }]}>2. Enter the 6-digit code</Text>
            <TextInput
              style={styles.codeInput}
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
                style={styles.primaryBtn}
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
              <Text style={styles.cancelBtnText}>Cancel</Text>
            </AnimatedPressable>
          </View>
        ) : hasVerifiedFactor ? (
          /* Already enrolled */
          <View style={styles.statusSection}>
            <View style={styles.statusBadge}>
              <Ionicons name="shield-checkmark" size={32} color={SUCCESS} />
              <Text style={styles.statusText}>2FA is enabled</Text>
            </View>
            <Text style={styles.statusDesc}>
              Your account is protected with two-factor authentication.
            </Text>

            {factors
              .filter((f) => f.status === 'verified')
              .map((f) => (
                <View key={f.id} style={styles.factorRow}>
                  <View>
                    <Text style={styles.factorName}>{f.friendly_name || 'Authenticator'}</Text>
                    <Text style={styles.factorType}>TOTP</Text>
                  </View>
                  <AnimatedPressable
                    onPress={() => handleUnenroll(f.id)}
                    accessibilityRole="button"
                    accessibilityLabel="Remove this factor"
                  >
                    <Text style={styles.removeText}>Remove</Text>
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
            <Text style={styles.statusDesc}>
              Protect your account by enabling two-factor authentication with an authenticator app.
            </Text>

            {enrolling ? (
              <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 24 }} />
            ) : (
              <AnimatedPressable
                style={styles.primaryBtn}
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  scroll: {
    paddingHorizontal: 24,
    paddingVertical: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: NAVY,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: MUTED,
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
    color: SUCCESS,
  },
  statusDesc: {
    fontSize: 14,
    color: MUTED,
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
    borderColor: BORDER,
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
  },
  factorName: {
    fontSize: 15,
    fontWeight: '600',
    color: NAVY,
  },
  factorType: {
    fontSize: 12,
    color: MUTED,
    marginTop: 2,
  },
  removeText: {
    fontSize: 14,
    fontWeight: '600',
    color: DANGER,
  },
  enrollSection: {
    alignItems: 'center',
  },
  stepTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: NAVY,
    alignSelf: 'flex-start',
    marginBottom: 6,
  },
  stepDesc: {
    fontSize: 14,
    color: MUTED,
    lineHeight: 22,
    alignSelf: 'flex-start',
    marginBottom: 16,
  },
  qrContainer: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: BORDER,
  },
  qrImage: {
    width: 200,
    height: 200,
  },
  codeInput: {
    backgroundColor: INPUT_BG,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
    paddingHorizontal: 20,
    paddingVertical: 16,
    fontSize: 24,
    fontWeight: '700',
    letterSpacing: 8,
    textAlign: 'center',
    color: NAVY,
    width: '100%',
    marginTop: 8,
  },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: TIFFANY,
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
    color: MUTED,
  },
});
