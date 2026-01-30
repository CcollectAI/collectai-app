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
import { router, Stack } from 'expo-router';
import { dataProvider } from '@/data';

export default function QuickScanScreen() {
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
    <>
      <Stack.Screen options={{ headerTitle: 'QuickScan' }} />
      <SafeAreaView style={styles.container}>
        <View style={styles.content}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.status}>{status}</Text>
        </View>
      </SafeAreaView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F7FA',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  status: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    paddingHorizontal: 32,
  },
});
