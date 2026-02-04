/**
 * Barcode / ISBN Scanner Screen
 *
 * Scans barcodes (EAN-13, UPC-A, ISBN) and triggers lookupByBarcode.
 * Flow: scan → detect codeType + value → show prefill card → confirm → save
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  TextInput,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { dataProvider, type BarcodeLookupResult } from '@/data';

type ScanState = 'scanning' | 'loading' | 'result' | 'error';

export default function BarcodeScanScreen() {
  const { colors } = useAppTheme();

  const [permission, requestPermission] = useCameraPermissions();
  const [scanState, setScanState] = useState<ScanState>('scanning');
  const [scannedCode, setScannedCode] = useState<{ type: string; value: string } | null>(null);
  const [lookupResult, setLookupResult] = useState<BarcodeLookupResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualIsbn, setManualIsbn] = useState('');
  const [isManualSubmitting, setIsManualSubmitting] = useState(false);

  // Handle barcode detection
  const handleBarcodeScanned = async (result: BarcodeScanningResult) => {
    if (scanState !== 'scanning') return;

    const { type, data } = result;

    // Only accept relevant barcode types
    const validTypes = ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'isbn'];
    const normalizedType = type.toLowerCase().replace('-', '_');

    if (!validTypes.some(t => normalizedType.includes(t))) {
      return; // Ignore unsupported barcode types
    }

    setScannedCode({ type: normalizedType, value: data });
    setScanState('loading');

    try {
      const prefill = await dataProvider.lookupByBarcode(data, { codeType: normalizedType });
      setLookupResult(prefill);
      setScanState('result');
    } catch (err) {
      console.error('[BarcodeScan] Lookup error:', err);
      setErrorMessage('Could not find product information. Try manual search.');
      setScanState('error');
    }
  };

  // Handle manual ISBN submission
  const handleManualSubmit = async () => {
    const cleaned = manualIsbn.replace(/[\s-]/g, '');

    // Validate ISBN length (10 or 13 digits)
    if (cleaned.length < 10 || cleaned.length > 13) {
      setErrorMessage('Please enter a valid ISBN (10 or 13 digits)');
      setScanState('error');
      return;
    }

    Keyboard.dismiss();
    setIsManualSubmitting(true);
    setScannedCode({ type: 'manual', value: cleaned });
    setScanState('loading');

    try {
      const prefill = await dataProvider.lookupByBarcode(cleaned, {
        codeType: 'isbn',
        source: 'manual'
      });
      setLookupResult(prefill);
      setScanState('result');
    } catch (err) {
      console.error('[BarcodeScan] Manual lookup error:', err);
      setErrorMessage('Could not find product information. Check the ISBN and try again.');
      setScanState('error');
    } finally {
      setIsManualSubmitting(false);
    }
  };

  // Reset to scanning state
  const handleRescan = () => {
    setScannedCode(null);
    setLookupResult(null);
    setErrorMessage(null);
    setManualIsbn('');
    setScanState('scanning');
  };

  // Save item to collection
  const handleSaveToCollection = () => {
    if (!lookupResult) return;

    // Navigate to add-manual with prefilled data
    router.push({
      pathname: '/add-manual',
      params: {
        prefillTitle: lookupResult.title || '',
        prefillCategory: lookupResult.categoryId || '',
        prefillPrice: lookupResult.priceBand?.q50?.toString() || '',
        prefillBarcode: scannedCode?.value || '',
        prefillCollections: lookupResult.collections?.join(',') || '',
      },
    });
  };

  // Add to watchlist instead
  const handleAddToWatchlist = () => {
    if (!lookupResult) return;

    router.push({
      pathname: '/add-manual',
      params: {
        prefillTitle: lookupResult.title || '',
        prefillCategory: lookupResult.categoryId || '',
        prefillBarcode: scannedCode?.value || '',
        mode: 'watchlist',
      },
    });
  };

  // Permission not determined yet
  if (!permission) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </SafeAreaView>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.permissionContainer}>
          <Ionicons name="camera-outline" size={64} color={colors.muted} />
          <Text style={[styles.permissionTitle, { color: colors.text }]}>
            Camera Permission Required
          </Text>
          <Text style={[styles.permissionText, { color: colors.muted }]}>
            We need camera access to scan barcodes and ISBN codes.
          </Text>
          <TouchableOpacity
            style={[styles.permissionButton, { backgroundColor: colors.accent }]}
            onPress={requestPermission}
          >
            <Text style={[styles.permissionButtonText, { color: colors.card }]}>Grant Permission</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Text style={[styles.backButtonText, { color: colors.muted }]}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      {/* Header - compact, no extra padding */}
      <View style={[styles.header, { backgroundColor: colors.background }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBack}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Scan Barcode</Text>
        <View style={styles.headerRight} />
      </View>

      {scanState === 'scanning' && (
        <KeyboardAvoidingView
          style={styles.scanningContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 100 : 20}
        >
          <View style={styles.cameraContainer}>
            <CameraView
              style={styles.camera}
              facing="back"
              barcodeScannerSettings={{
                barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128'],
              }}
              onBarcodeScanned={handleBarcodeScanned}
            >
              {/* Scan overlay */}
              <View style={styles.scanOverlay}>
                <View style={styles.scanFrame}>
                  <View style={[styles.scanCorner, styles.scanCornerTL]} />
                  <View style={[styles.scanCorner, styles.scanCornerTR]} />
                  <View style={[styles.scanCorner, styles.scanCornerBL]} />
                  <View style={[styles.scanCorner, styles.scanCornerBR]} />
                </View>
                <Text style={styles.scanHint}>
                  Point camera at barcode or ISBN
                </Text>
              </View>
            </CameraView>
          </View>

          {/* Manual ISBN Entry - Upgraded card design */}
          <ScrollView
            style={styles.manualEntryScroll}
            contentContainerStyle={styles.manualEntryScrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={[styles.manualEntryCard, { backgroundColor: colors.card }]}>
              <Text style={[styles.manualEntryTitle, { color: colors.text }]}>
                Manual Entry
              </Text>
              <Text style={[styles.manualEntryHelper, { color: colors.muted }]}>
                Can't scan? Type the ISBN code from the back cover
              </Text>
              <View style={styles.manualEntryRow}>
                <TextInput
                  style={[styles.manualInput, {
                    backgroundColor: colors.background,
                    borderColor: colors.border,
                    color: colors.text
                  }]}
                  placeholder="978-0-123456-78-9"
                  placeholderTextColor={colors.muted}
                  value={manualIsbn}
                  onChangeText={setManualIsbn}
                  keyboardType="number-pad"
                  maxLength={17}
                  returnKeyType="search"
                  onSubmitEditing={handleManualSubmit}
                  accessibilityLabel="ISBN input field"
                  accessibilityHint="Enter 10 or 13 digit ISBN number"
                />
                <TouchableOpacity
                  style={[styles.manualSubmitButton, {
                    backgroundColor: colors.accent,
                    opacity: manualIsbn.length < 10 || isManualSubmitting ? 0.5 : 1
                  }]}
                  onPress={handleManualSubmit}
                  disabled={manualIsbn.length < 10 || isManualSubmitting}
                  accessibilityLabel="Look up ISBN"
                  accessibilityRole="button"
                >
                  {isManualSubmitting ? (
                    <ActivityIndicator size="small" color={colors.card} />
                  ) : (
                    <Ionicons name="search" size={20} color={colors.card} />
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      )}

      {scanState === 'loading' && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.text }]}>
            Looking up product...
          </Text>
          {scannedCode && (
            <Text style={[styles.codeText, { color: colors.muted }]}>
              {scannedCode.type.toUpperCase()}: {scannedCode.value}
            </Text>
          )}
        </View>
      )}

      {scanState === 'result' && lookupResult && (
        <ScrollView style={styles.resultContainer} contentContainerStyle={styles.resultContent}>
          {/* Product card */}
          <View style={[styles.productCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.productHeader}>
              <Ionicons name="checkmark-circle" size={32} color={colors.accent} />
              <Text style={[styles.productFound, { color: colors.text }]}>Product Found</Text>
            </View>

            <Text style={[styles.productTitle, { color: colors.text }]}>
              {lookupResult.title || 'Unknown Product'}
            </Text>

            {lookupResult.categoryId && (
              <View style={styles.productMeta}>
                <Ionicons name="folder-outline" size={16} color={colors.muted} />
                <Text style={[styles.productMetaText, { color: colors.muted }]}>
                  {lookupResult.categoryId}
                </Text>
              </View>
            )}

            {lookupResult.collections && lookupResult.collections.length > 0 && (
              <View style={styles.collectionsRow}>
                {lookupResult.collections.map((tag) => (
                  <View key={tag} style={[styles.collectionTag, { backgroundColor: colors.accent + '20' }]}>
                    <Text style={[styles.collectionTagText, { color: colors.accent }]}>{tag}</Text>
                  </View>
                ))}
              </View>
            )}

            {lookupResult.priceBand && (
              <View style={[styles.priceCard, { backgroundColor: colors.background }]}>
                <Text style={[styles.priceLabel, { color: colors.muted }]}>Estimated Price</Text>
                <Text style={[styles.priceValue, { color: colors.text }]}>
                  €{lookupResult.priceBand.q50.toFixed(2)}
                </Text>
                <Text style={[styles.priceRange, { color: colors.muted }]}>
                  Range: €{lookupResult.priceBand.q10.toFixed(2)} – €{lookupResult.priceBand.q90.toFixed(2)}
                </Text>
              </View>
            )}

            {scannedCode && (
              <Text style={[styles.barcodeInfo, { color: colors.muted }]}>
                {scannedCode.type.toUpperCase()}: {scannedCode.value}
              </Text>
            )}
          </View>

          {/* Action buttons - Reordered: Scan another left, Save right */}
          <View style={styles.actionButtonsRow}>
            <TouchableOpacity
              style={[styles.secondaryButtonHalf, { borderColor: colors.border }]}
              onPress={handleRescan}
            >
              <Ionicons name="scan-outline" size={18} color={colors.text} />
              <Text style={[styles.secondaryButtonText, { color: colors.text }]}>Scan Another</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.primaryButtonHalf, { backgroundColor: colors.accent }]}
              onPress={handleSaveToCollection}
            >
              <Ionicons name="add-circle-outline" size={18} color={colors.card} />
              <Text style={[styles.primaryButtonText, { color: colors.card }]}>Save</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={[styles.watchlistButton, { borderColor: colors.border }]}
            onPress={handleAddToWatchlist}
          >
            <Ionicons name="eye-outline" size={18} color={colors.muted} />
            <Text style={[styles.watchlistButtonText, { color: colors.muted }]}>Add to Watchlist Instead</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      {scanState === 'error' && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={64} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>Not Found</Text>
          <Text style={[styles.errorText, { color: colors.muted }]}>
            {errorMessage}
          </Text>
          {scannedCode && (
            <Text style={[styles.codeText, { color: colors.muted }]}>
              Scanned: {scannedCode.value}
            </Text>
          )}
          <View style={styles.errorActions}>
            <TouchableOpacity
              style={[styles.primaryButton, { backgroundColor: colors.accent }]}
              onPress={handleRescan}
            >
              <Ionicons name="scan-outline" size={20} color={colors.card} />
              <Text style={[styles.primaryButtonText, { color: colors.card }]}>Try Again</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.secondaryButton, { borderColor: colors.border }]}
              onPress={() => router.push('/add-manual')}
            >
              <Text style={[styles.secondaryButtonText, { color: colors.text }]}>Add Manually</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 8,
  },
  scanningContainer: {
    flex: 1,
  },
  headerBack: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  headerRight: {
    width: 32,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  permissionText: {
    fontSize: 15,
    textAlign: 'center',
    marginBottom: 24,
  },
  permissionButton: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  permissionButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  backButton: {
    marginTop: 16,
    padding: 8,
  },
  backButtonText: {
    fontSize: 15,
  },
  cameraContainer: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },
  scanOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  scanFrame: {
    width: 280,
    height: 180,
    position: 'relative',
  },
  scanCorner: {
    position: 'absolute',
    width: 24,
    height: 24,
    borderColor: '#fff',
  },
  scanCornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 3,
    borderLeftWidth: 3,
  },
  scanCornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 3,
    borderRightWidth: 3,
  },
  scanCornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
  },
  scanCornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 3,
    borderRightWidth: 3,
  },
  scanHint: {
    color: '#fff',
    fontSize: 15,
    marginTop: 24,
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  loadingText: {
    fontSize: 17,
    fontWeight: '500',
    marginTop: 16,
  },
  codeText: {
    fontSize: 13,
    marginTop: 8,
    fontFamily: 'monospace',
  },
  resultContainer: {
    flex: 1,
  },
  resultContent: {
    padding: 16,
  },
  productCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  productHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  productFound: {
    fontSize: 16,
    fontWeight: '600',
  },
  productTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  productMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  productMetaText: {
    fontSize: 14,
  },
  collectionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
  },
  collectionTag: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  collectionTagText: {
    fontSize: 12,
    fontWeight: '500',
  },
  priceCard: {
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  priceLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  priceValue: {
    fontSize: 24,
    fontWeight: '700',
  },
  priceRange: {
    fontSize: 12,
    marginTop: 4,
  },
  barcodeInfo: {
    fontSize: 12,
    fontFamily: 'monospace',
    marginTop: 8,
  },
  actionButtons: {
    gap: 12,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 10,
  },
  primaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 14,
    borderRadius: 10,
  },
  primaryButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
  secondaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
  },
  secondaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: '500',
  },
  watchlistButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    marginTop: 8,
  },
  watchlistButtonText: {
    fontSize: 13,
  },
  rescanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
  },
  rescanButtonText: {
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  errorText: {
    fontSize: 15,
    textAlign: 'center',
    marginBottom: 8,
  },
  errorActions: {
    marginTop: 24,
    gap: 12,
    width: '100%',
  },
  manualEntryScroll: {
    maxHeight: 200,
  },
  manualEntryScrollContent: {
    flexGrow: 1,
  },
  manualEntryCard: {
    margin: 16,
    marginTop: 12,
    padding: 20,
    borderRadius: 16,
  },
  manualEntryTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 6,
  },
  manualEntryHelper: {
    fontSize: 13,
    marginBottom: 16,
    lineHeight: 18,
  },
  manualEntryRow: {
    flexDirection: 'row',
    gap: 10,
  },
  manualInput: {
    flex: 1,
    height: 52,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 16,
    fontSize: 17,
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  manualSubmitButton: {
    width: 52,
    height: 52,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
