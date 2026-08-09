/**
 * Barcode / ISBN Scanner Screen
 *
 * Scans barcodes (EAN-13, UPC-A, ISBN) and triggers lookupByBarcode.
 * Flow: scan → detect codeType + value → show prefill card → confirm → save
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { track } from '@/analytics/track';
import React, { useCallback, useEffect, useState } from 'react';
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
import { safeGoBack } from '@/lib/goBack';

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

  // Hand off an unrecognised scan to manual entry, carrying the barcode so it
  // is not lost. Mirrors QuickScan's low-confidence path (see ARCHITECTURE.md
  // "QuickScan client guardrail"); before this, the only option offered was
  // Save, which filed an item called "Unknown item" with no category.
  const handleAddManually = useCallback(() => {
    const code = scannedCode?.value;
    router.push({
      pathname: '/add-manual',
      params: {
        ...(lookupResult?.categoryId ? { category: lookupResult.categoryId } : {}),
        ...(lookupResult?.title ? { name: lookupResult.title } : {}),
        ...(code ? { attrs: JSON.stringify({ barcode: code }) } : {}),
      },
    });
  }, [router, scannedCode, lookupResult]);

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
      // Fallback: hand the scan to add-manual so nothing typed or scanned is
      // lost. Uses the SAME param names as handleAddManually above, which are
      // the ones app/add-manual.tsx actually reads
      // (`imageUri | category | name | condition | attrs`).
      //
      // It used to send seven `prefill*` keys. add-manual reads none of them, so
      // every one was dropped in transit and this screen — the recovery path,
      // reached at the exact moment a save has already failed — opened a
      // completely empty form. The primary button one function up had the right
      // names all along: one handoff was fixed and its twin was left behind
      // (learning_duplicate_impl_silently_drops_the_fix). Nothing errored,
      // because expo-router types params as an open record; `npm run
      // check:params` is what fails on it now.
      //
      // priceBand.q50, collections, identification_method and subtype_id have no
      // field on add-manual to land in, so they are deliberately NOT sent rather
      // than sent under invented names. The estimate is recomputed there anyway.
      router.push({
        pathname: '/add-manual',
        params: {
          ...(lookupResult.categoryId ? { category: lookupResult.categoryId } : {}),
          ...(lookupResult.title ? { name: lookupResult.title } : {}),
          ...(scannedCode?.value
            ? { attrs: JSON.stringify({ barcode: scannedCode.value }) }
            : {}),
        },
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Add to watchlist instead
  // Adds to the WATCHLIST, which is what the button says.
  //
  // It used to push `/add-manual` with `mode: 'watchlist'` plus three `prefill*`
  // params. add-manual reads none of those four keys and has no watchlist mode
  // at all, so the button opened the empty ADD-TO-COLLECTION form — the opposite
  // of what a user asking to watch something wants, and it would have filed the
  // item as owned. Nothing errored: expo-router accepts any param key, so
  // `mode` looked like a feature and was a no-op (found by
  // scripts/check-route-param-handoff.mjs, 2026-08-09).
  //
  // Writes directly through dataProvider rather than routing anywhere: a
  // watchlist row needs a title and a category, and both are already in hand
  // from the lookup. Sending the user to a form to retype them is the same
  // double work as the sell flow.
  const [watching, setWatching] = useState(false);
  const [watched, setWatched] = useState(false);

  const handleAddToWatchlist = useCallback(async () => {
    if (!lookupResult || watching || watched) return;
    const title = (lookupResult.title || '').trim();
    if (!title) {
      // A watchlist row keyed on an empty title is unmatchable and unreadable.
      showToast({ message: 'This scan has no title to watch yet', type: 'warning' });
      return;
    }
    setWatching(true);
    try {
      await dataProvider.addWatchlistItem({
        title,
        // CreateWatchlistInput requires a category; the scan may not have one and
        // '' would write a row the category filters can never surface.
        category: lookupResult.categoryId || 'other',
        notes: scannedCode?.value ? `Barcode ${scannedCode.value}` : undefined,
      });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      setWatched(true);
      showToast({ message: 'Added to your watchlist', type: 'success' });
    } catch (err) {
      logger.error('[BarcodeScan] add to watchlist failed:', err);
      showToast({
        message: (err as Error)?.message || 'Could not add to your watchlist',
        type: 'error',
      });
    } finally {
      setWatching(false);
    }
  }, [lookupResult, scannedCode, watching, watched, showToast, settings.hapticsEnabled]);

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
        onCancel={() => safeGoBack(router)}
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
            {/* expo-camera warns "<CameraView> does not support children.
                This may lead to inconsistent behaviour or crashes." The overlay
                is therefore a SIBLING positioned over the camera rather than a
                child. Layering is unchanged: the camera fills the container and
                the overlay, rendered after it, paints on top. */}
            <CameraView
              style={StyleSheet.absoluteFill}
              facing="back"
              barcodeScannerSettings={{
                barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128'],
              }}
              onBarcodeScanned={handleBarcodeScanned}
            />

            {/* Scan overlay */}
            <View style={[StyleSheet.absoluteFill, styles.scanOverlay]} pointerEvents="none">
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
          onAddManually={handleAddManually}
          onAddToWatchlist={handleAddToWatchlist}
          watchlistState={watched ? 'done' : watching ? 'saving' : 'idle'}
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
