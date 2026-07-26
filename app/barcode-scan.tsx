/**
 * Barcode / ISBN Scanner Screen
 *
 * Scans barcodes (EAN-13, UPC-A, ISBN) and triggers lookupByBarcode.
 * Flow: scan → detect codeType + value → show prefill card → confirm → save
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { track } from '@/analytics/track';
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
// SafeAreaView removed — Stack header handles safe area
import { router, Stack } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { useScannerTheme } from '@/hooks/useAppTheme';
import { dataProvider, type BarcodeLookupResult } from '@/data';
import { collectorsApi, type IntakeResultResponse, getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import CatalogSuggestionModal, { type CatalogSuggestionSource } from '@/components/CatalogSuggestionModal';
import { BarcodeResultCard } from '@/components/barcode/BarcodeResultCard';
import { BarcodeModeSelector } from '@/components/barcode/BarcodeModeSelector';
// Imported from the file, not the quickscan barrel, to avoid pulling the whole
// QuickScan component set into this screen.
import { PermissionScreen } from '@/components/quickscan/PermissionScreen';

/** Barcode types accepted by the scanner */
const SUPPORTED_BARCODE_TYPES = ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'isbn'] as const;

type ScanState = 'scanning' | 'loading' | 'result' | 'error';
type InputMode = 'camera' | 'url';

function BarcodeScanScreen() {
  const { colors } = useScannerTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [permission, requestPermission] = useCameraPermissions();
  const [scanState, setScanState] = useState<ScanState>('scanning');
  const [scannedCode, setScannedCode] = useState<{ type: string; value: string } | null>(null);
  const [lookupResult, setLookupResult] = useState<BarcodeLookupResult | null>(null);
  const [intakeResult, setIntakeResult] = useState<IntakeResultResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualIsbn, setManualIsbn] = useState('');
  const [isManualSubmitting, setIsManualSubmitting] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>('camera');
  const [urlInput, setUrlInput] = useState('');
  const [isUrlSubmitting, setIsUrlSubmitting] = useState(false);
  const [affiliateLink, setAffiliateLink] = useState<{ url: string; label: string } | null>(null);

  // Billing / paywall state
  const [userPlan, setUserPlan] = useState<BillingStatus['plan']>('free');
  useEffect(() => {
    let cancelled = false;
    getBillingStatus()
      .then((b) => { if (!cancelled) setUserPlan(b.plan); })
      .catch(() => {}); // default to 'free' on error
    return () => { cancelled = true; };
  }, []);

  // Catalog learning modal state
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);
  const [catalogModalSource, setCatalogModalSource] = useState<CatalogSuggestionSource>('barcode');
  const [catalogModalInputData, setCatalogModalInputData] = useState<Record<string, unknown>>({});
  const [catalogModalPrefillName, setCatalogModalPrefillName] = useState('');

  // Handle barcode detection
  const handleBarcodeScanned = async (result: BarcodeScanningResult) => {
    if (scanState !== 'scanning') return;

    const { type, data } = result;

    // Only accept relevant barcode types
    const normalizedType = type.toLowerCase().replace('-', '_');

    if (!SUPPORTED_BARCODE_TYPES.some(t => normalizedType.includes(t))) {
      return; // Ignore unsupported barcode types
    }

    setScannedCode({ type: normalizedType, value: data });
    setScanState('loading');

    try {
      // Call the Intake Agent for enriched barcode lookup
      const intake = await collectorsApi.processIntake(data, normalizedType);
      setIntakeResult(intake);

      // Also build a compatible BarcodeLookupResult for the existing UI
      const prefill: BarcodeLookupResult = {
        title: intake.name,
        categoryId: intake.category_id,
        subtypeId: intake.subtype_id,
        taxonomyVersion: intake.taxonomy_version,
        collections: [],
        attributes: intake.attributes,
        missingRequired: (!intake.name ? ['title'] : []).concat(!intake.category_id ? ['categoryId'] : []),
        priceBand: intake.price_band ?? null,
        rationale: intake.rationale,
        barcode: intake.barcode ?? data,
        barcodeType: intake.barcode_type ?? normalizedType,
        imageUrl: intake.image_url,
      };
      setLookupResult(prefill);
      setScanState('result');

      // Show catalog suggestion modal if intake flagged a miss
      if (intake.catalog_miss) {
        setCatalogModalSource('barcode');
        setCatalogModalInputData({ barcode: data, barcode_type: normalizedType });
        setCatalogModalPrefillName(intake.name || '');
        setCatalogModalVisible(true);
      }
    } catch (err) {
      logger.error('[BarcodeScan] Intake error, falling back to direct lookup:', err);
      // Fallback to direct barcode lookup if intake agent fails
      try {
        const prefill = await dataProvider.lookupByBarcode(data, { codeType: normalizedType });
        setLookupResult(prefill);
        setIntakeResult(null);
        setScanState('result');
      } catch (fallbackErr) {
        logger.error('[BarcodeScan] Fallback lookup error:', fallbackErr);
        setErrorMessage('Could not find product information. Try manual search.');
        setScanState('error');
        // Show catalog suggestion modal on complete failure
        setCatalogModalSource('barcode');
        setCatalogModalInputData({ barcode: data, barcode_type: normalizedType });
        setCatalogModalPrefillName('');
        setCatalogModalVisible(true);
      }
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
      // Call the Intake Agent for enriched manual ISBN lookup
      const intake = await collectorsApi.processIntake(cleaned, 'isbn');
      setIntakeResult(intake);

      const prefill: BarcodeLookupResult = {
        title: intake.name,
        categoryId: intake.category_id,
        subtypeId: intake.subtype_id,
        taxonomyVersion: intake.taxonomy_version,
        collections: [],
        attributes: intake.attributes,
        missingRequired: (!intake.name ? ['title'] : []).concat(!intake.category_id ? ['categoryId'] : []),
        priceBand: intake.price_band ?? null,
        rationale: intake.rationale,
        barcode: intake.barcode ?? cleaned,
        barcodeType: intake.barcode_type ?? 'isbn',
        imageUrl: intake.image_url,
      };
      setLookupResult(prefill);
      setScanState('result');

      // Show catalog suggestion modal if intake flagged a miss
      if (intake.catalog_miss) {
        setCatalogModalSource('barcode');
        setCatalogModalInputData({ barcode: cleaned, barcode_type: 'isbn' });
        setCatalogModalPrefillName(intake.name || '');
        setCatalogModalVisible(true);
      }
    } catch (err) {
      logger.error('[BarcodeScan] Intake manual error, falling back:', err);
      try {
        const prefill = await dataProvider.lookupByBarcode(cleaned, {
          codeType: 'isbn',
        });
        setLookupResult(prefill);
        setIntakeResult(null);
        setScanState('result');
      } catch (fallbackErr) {
        logger.error('[BarcodeScan] Fallback manual lookup error:', fallbackErr);
        setErrorMessage('Could not find product information. Check the ISBN and try again.');
        setScanState('error');
        // Show catalog suggestion modal on complete failure
        setCatalogModalSource('barcode');
        setCatalogModalInputData({ barcode: cleaned, barcode_type: 'isbn' });
        setCatalogModalPrefillName('');
        setCatalogModalVisible(true);
      }
    } finally {
      setIsManualSubmitting(false);
    }
  };

  // Handle URL import
  const handleUrlSubmit = async () => {
    const trimmed = urlInput.trim();
    if (!trimmed || !trimmed.startsWith('http')) {
      setErrorMessage('Please enter a valid URL starting with http:// or https://');
      setScanState('error');
      return;
    }

    Keyboard.dismiss();
    setIsUrlSubmitting(true);
    setScannedCode({ type: 'url', value: trimmed });
    setScanState('loading');

    try {
      const intake = await collectorsApi.processIntakeUrl(trimmed);
      setIntakeResult(intake);

      const prefill: BarcodeLookupResult = {
        title: intake.name,
        categoryId: intake.category_id,
        subtypeId: intake.subtype_id,
        taxonomyVersion: intake.taxonomy_version,
        collections: [],
        attributes: intake.attributes,
        missingRequired: (!intake.name ? ['title'] : []).concat(!intake.category_id ? ['categoryId'] : []),
        priceBand: intake.price_band ?? null,
        rationale: intake.rationale,
        barcode: undefined,
        barcodeType: undefined,
        imageUrl: intake.image_url,
      };
      setLookupResult(prefill);
      setScanState('result');

      // Show catalog suggestion modal if intake flagged a miss
      if (intake.catalog_miss) {
        setCatalogModalSource('url');
        setCatalogModalInputData({ url: trimmed });
        setCatalogModalPrefillName(intake.name || '');
        setCatalogModalVisible(true);
      }
    } catch (err) {
      logger.error('[BarcodeScan] URL import error:', err);
      setErrorMessage('Could not import from this URL. Check the link and try again.');
      setScanState('error');
      // Show catalog suggestion modal on URL import failure
      setCatalogModalSource('url');
      setCatalogModalInputData({ url: trimmed });
      setCatalogModalPrefillName('');
      setCatalogModalVisible(true);
    } finally {
      setIsUrlSubmitting(false);
    }
  };

  // Fetch affiliate link when a product is identified
  useEffect(() => {
    if (scanState !== 'result' || !lookupResult?.title) {
      setAffiliateLink(null);
      return;
    }
    let cancelled = false;
    collectorsApi.getAffiliateLinks(lookupResult.title, lookupResult.categoryId || undefined, 1)
      .then((data) => {
        if (!cancelled && data.links.length > 0) {
          setAffiliateLink({ url: data.links[0].affiliate_url, label: data.links[0].label });
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [scanState, lookupResult?.title, lookupResult?.categoryId]);

  // Reset to scanning state
  const handleRescan = () => {
    setScannedCode(null);
    setLookupResult(null);
    setIntakeResult(null);
    setErrorMessage(null);
    setManualIsbn('');
    setUrlInput('');
    setAffiliateLink(null);
    setScanState('scanning');
  };

  // Save item to collection
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveToCollection = async () => {
    if (!lookupResult) return;

    setIsSaving(true);
    try {
      const saved = await collectorsApi.intakeSave({
        title: lookupResult.title || 'Unknown item',
        category: lookupResult.categoryId || undefined,
        condition: undefined,
        subtype_id: intakeResult?.subtype_id || lookupResult.subtypeId || undefined,
        taxonomy_version: intakeResult?.taxonomy_version || lookupResult.taxonomyVersion || undefined,
        attributes: (intakeResult?.attributes || lookupResult.attributes || {}) as Record<string, unknown>,
        images: lookupResult.imageUrl ? [lookupResult.imageUrl] : [],
        barcode: scannedCode?.value || undefined,
        estimated_price: lookupResult.priceBand?.q50 || undefined,
      });

      track({ name: 'item_added', properties: { source: 'barcode', category: lookupResult?.categoryId ?? undefined } });

      // Navigate to the new item detail
      router.replace({
        pathname: '/item/[id]',
        params: {
          id: saved.id,
          name: saved.title,
          category: saved.category || lookupResult.categoryId || '',
          value: lookupResult.priceBand?.q50?.toString() || '0',
          q10: lookupResult.priceBand?.q10?.toString() || '',
          q50: lookupResult.priceBand?.q50?.toString() || '',
          q90: lookupResult.priceBand?.q90?.toString() || '',
          confidence: lookupResult.priceBand?.confidence?.toString() || '',
          imageUri: lookupResult.imageUrl || '',
        },
      });
    } catch (err) {
      logger.error('[BarcodeScan] Save to collection error:', err);
      showToast({ message: 'Auto-save failed, opening manual entry', type: 'warning' });
      // Fallback: navigate to add-manual with prefilled data
      router.push({
        pathname: '/add-manual',
        params: {
          prefillTitle: lookupResult.title || '',
          prefillCategory: lookupResult.categoryId || '',
          prefillPrice: lookupResult.priceBand?.q50?.toString() || '',
          prefillBarcode: scannedCode?.value || '',
          prefillCollections: lookupResult.collections?.join(',') || '',
          prefillMethod: intakeResult?.identification_method || 'barcode',
          prefillSubtype: intakeResult?.subtype_id || '',
        },
      });
    } finally {
      setIsSaving(false);
    }
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
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <PermissionScreen
        onGrant={requestPermission}
        onCancel={() => router.back()}
        hapticsEnabled={settings.hapticsEnabled}
        canAskAgain={permission.canAskAgain}
        message="We need camera access to scan barcodes and ISBN codes."
        colors={colors}
      />
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Scan Barcode' }} />

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

          <BarcodeModeSelector
            manualIsbn={manualIsbn}
            onChangeIsbn={setManualIsbn}
            onSubmit={handleManualSubmit}
            isSubmitting={isManualSubmitting}
            hapticsEnabled={settings.hapticsEnabled}
          />
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
        <BarcodeResultCard
          lookupResult={lookupResult}
          intakeResult={intakeResult}
          scannedCode={scannedCode}
          affiliateLink={affiliateLink}
          isSaving={isSaving}
          currency={settings.currency}
          hapticsEnabled={settings.hapticsEnabled}
          onRescan={handleRescan}
          onSave={handleSaveToCollection}
          onAddToWatchlist={handleAddToWatchlist}
        />
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
            <AnimatedPressable
              style={[styles.primaryButton, { backgroundColor: colors.accent }]}
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); handleRescan(); }}
              accessibilityRole="button"
              accessibilityLabel="Try scanning again"
            >
              <Ionicons name="scan-outline" size={20} color={colors.card} />
              <Text style={[styles.primaryButtonText, { color: colors.card }]}>Try Again</Text>
            </AnimatedPressable>
            <AnimatedPressable
              style={[styles.secondaryButton, { borderColor: colors.border }]}
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push('/add-manual'); }}
              accessibilityRole="button"
              accessibilityLabel="Add item manually"
            >
              <Text style={[styles.secondaryButtonText, { color: colors.text }]}>Add Manually</Text>
            </AnimatedPressable>
          </View>
        </View>
      )}

      {/* Catalog Learning Suggestion Modal */}
      <CatalogSuggestionModal
        visible={catalogModalVisible}
        onDismiss={() => setCatalogModalVisible(false)}
        source={catalogModalSource}
        prefillName={catalogModalPrefillName}
        inputData={catalogModalInputData}
      />
    </View>
  );
}

export default function BarcodeScanScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Barcode Scan">
      <BarcodeScanScreen />
    </ScreenErrorBoundary>
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
  // Permission styles removed — this screen now renders the shared
  // PermissionScreen component instead of its own copy of that UI.
  cameraContainer: {
    flex: 1,
    borderRadius: 16,
    marginHorizontal: 12,
    marginTop: 4,
    overflow: 'hidden',
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
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '500',
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
  _modeToggleRemoved: {
    // Mode toggle removed — barcode scan is now camera-only
  },
  urlImportContainer: {
    flex: 1,
    justifyContent: 'center',
    padding: 16,
  },
  urlInput: {
    height: 52,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 16,
    fontSize: 15,
    marginBottom: 12,
  },
  urlSubmitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 10,
  },
  urlExamplesCard: {
    margin: 0,
    marginTop: 16,
    padding: 16,
    borderRadius: 12,
  },
  urlExamplesTitle: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  urlExamplesText: {
    fontSize: 13,
    lineHeight: 18,
  },
});
