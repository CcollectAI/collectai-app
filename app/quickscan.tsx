/**
 * QuickScan capture screen.
 * Opens camera → captures image → calls dataProvider.quickscanSingle() → navigates to item card in draft mode.
 */
import React, { useCallback, useState, useEffect } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { dataProvider } from '@/data';
import { featureFlags } from '@/config/featureFlags';
import { fireHaptic, HapticIntent, confidenceToIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';

export default function QuickScanScreen() {
  const { colors } = useAppTheme();
  const [status, setStatus] = useState('Requesting camera...');
  const [loading, setLoading] = useState(true);

  const runScan = useCallback(async () => {
    // Request camera permission
    const { status: permStatus } = await ImagePicker.requestCameraPermissionsAsync();
    if (permStatus !== 'granted') {
      Alert.alert(
        'Camera permission required',
        'Enable camera access to scan collectibles.',
        [{ text: 'OK', onPress: () => router.back() }]
      );
      return;
    }

    setStatus('Opening camera...');

    // Launch camera
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
    });

    if (result.canceled) {
      router.back();
      return;
    }

    const imageUri = result.assets?.[0]?.uri ?? null;
    if (!imageUri) {
      Alert.alert('Error', 'Failed to capture image.');
      router.back();
      return;
    }

    setStatus('Analyzing image...');

    try {
      const scanResult = await dataProvider.quickscanSingle();

      // Fire haptic based on confidence
      if (featureFlags.FEATURE_HAPTICS_MICRO_ANIMATIONS) {
        const intent = confidenceToIntent(scanResult.prediction.confidence);
        fireHaptic(intent);
      }

      // Navigate to item card in draft mode with scan results
      router.replace({
        pathname: '/item/[id]',
        params: {
          id: 'draft',
          draft: '1',
          name: scanResult.prediction.name,
          category: scanResult.attributes.category,
          condition: scanResult.attributes.conditionGuess ?? 'Not graded',
          value: String(scanResult.prediction.estimatedMid),
          q10: String(scanResult.prediction.estimatedLow),
          q50: String(scanResult.prediction.estimatedMid),
          q90: String(scanResult.prediction.estimatedHigh),
          confidence: String(Math.round(scanResult.prediction.confidence * 100)),
          imageUri: imageUri,
          notes: '',
        },
      });
    } catch (err: any) {
      console.warn('[QuickScan] error:', err);
      if (featureFlags.FEATURE_HAPTICS_MICRO_ANIMATIONS) {
        fireHaptic(HapticIntent.ALERT_TRIGGERED);
      }
      Alert.alert(
        'Scan failed',
        err?.message ?? 'Unable to analyze image. Please try again.',
        [{ text: 'OK', onPress: () => router.back() }]
      );
    }
  }, []);

  useEffect(() => {
    runScan();
  }, [runScan]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.content}>
        <View style={[styles.loadingCard, { backgroundColor: colors.card }]}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.status, { color: colors.text }]}>{status}</Text>
          <Text style={[styles.hint, { color: colors.muted }]}>
            Hold steady for best results
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  loadingCard: {
    padding: 32,
    borderRadius: 20,
    alignItems: 'center',
    gap: 16,
    width: '100%',
    maxWidth: 280,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  status: {
    fontSize: 17,
    fontWeight: '600',
    textAlign: 'center',
  },
  hint: {
    fontSize: 13,
    textAlign: 'center',
  },
});
