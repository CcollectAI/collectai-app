/**
 * Barcode / ISBN Scanner Screen
 *
 * Scans barcodes (EAN-13, UPC-A, ISBN) and triggers lookupByBarcode.
 * Flow: scan → detect codeType + value → show prefill card → confirm → save
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  TextInput,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { dataProvider, type BarcodeLookupResult } from '@/data';
import { collectorsApi, type IntakeResultResponse, getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import CatalogSuggestionModal, { type CatalogSuggestionSource } from '@/components/CatalogSuggestionModal';

/** Barcode types accepted by the scanner */
const SUPPORTED_BARCODE_TYPES = ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'isbn'] as const;

type ScanState = 'scanning' | 'loading' | 'result' | 'error';
type InputMode = 'camera' | 'url';

function BarcodeScanScreen() {
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
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
    getBillingStatus()
      .then((b) => setUserPlan(b.plan))
      .catch(() => {}); // default to 'free' on error
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
          source: 'manual'
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
        barcode: null,
        barcodeType: null,
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
    collectorsApi.getAffiliateLinks(lookupResult.title, lookupResult.categoryId || undefined, 1)
      .then((data) => {
        if (data.links.length > 0) {
          setAffiliateLink({ url: data.links[0].affiliate_url, label: data.links[0].label });
        }
      })
      .catch(() => {});
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
          <AnimatedPressable
            style={[styles.permissionButton, { backgroundColor: colors.accent }]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); requestPermission(); }}
            accessibilityRole="button"
            accessibilityLabel="Grant camera permission"
          >
            <Text style={[styles.permissionButtonText, { color: colors.card }]}>Grant Permission</Text>
          </AnimatedPressable>
          <AnimatedPressable style={styles.backButton} onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={[styles.backButtonText, { color: colors.muted }]}>Go Back</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.background }]}>
        <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }} style={styles.headerBack} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>
          {inputMode === 'camera' ? 'Scan EAN Barcode / ISBN' : 'Import from URL'}
        </Text>
        <ThemeToggleButton size={22} />
      </View>

      {/* Mode Toggle */}
      {scanState === 'scanning' && (
        <View style={styles.modeToggleRow}>
          <AnimatedPressable
            style={[
              styles.modeToggleButton,
              inputMode === 'camera'
                ? { backgroundColor: colors.accent }
                : { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 },
            ]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); setInputMode('camera'); }}
            accessibilityRole="button"
            accessibilityLabel="Switch to camera scan mode"
          >
            <Ionicons name="scan-outline" size={22} color={inputMode === 'camera' ? '#fff' : colors.text} />
            <Text style={[styles.modeToggleText, { color: inputMode === 'camera' ? '#fff' : colors.text }]}
              allowFontScaling={false}
            >
              EAN / ISBN
            </Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[
              styles.modeToggleButton,
              inputMode === 'url'
                ? { backgroundColor: colors.accent }
                : { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 },
            ]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              if (userPlan === 'free') {
                showToast({ message: 'URL import requires a Pro plan', type: 'warning' });
                router.push('/subscription');
                return;
              }
              setInputMode('url');
            }}
            accessibilityRole="button"
            accessibilityLabel="Switch to URL import mode"
          >
            <Ionicons name="link-outline" size={22} color={inputMode === 'url' ? '#fff' : colors.text} />
            <Text style={[styles.modeToggleText, { color: inputMode === 'url' ? '#fff' : colors.text }]}
              allowFontScaling={false}
            >
              Paste URL
            </Text>
            {userPlan === 'free' && (
              <Ionicons name="lock-closed" size={15} color={inputMode === 'url' ? '#fff' : colors.muted} />
            )}
          </AnimatedPressable>
        </View>
      )}

      {scanState === 'scanning' && inputMode === 'url' && (
        <KeyboardAvoidingView
          style={styles.scanningContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 100 : 20}
        >
          <View style={styles.urlImportContainer}>
            <View style={[styles.manualEntryCard, { backgroundColor: colors.card }]}>
              <Text style={[styles.manualEntryTitle, { color: colors.text }]}>
                Import from URL
              </Text>
              <Text style={[styles.manualEntryHelper, { color: colors.muted }]}>
                Paste a link from eBay, Mercari, StockX, TCGPlayer, BrickLink, or other marketplaces
              </Text>
              <TextInput
                style={[styles.urlInput, {
                  backgroundColor: colors.background,
                  borderColor: colors.border,
                  color: colors.text,
                }]}
                placeholder="https://ebay.com/itm/..."
                placeholderTextColor={colors.muted}
                value={urlInput}
                onChangeText={setUrlInput}
                keyboardType="url"
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="go"
                onSubmitEditing={handleUrlSubmit}
                accessibilityLabel="URL input field"
                accessibilityHint="Paste a marketplace listing URL"
              />
              <AnimatedPressable
                style={[styles.urlSubmitButton, {
                  backgroundColor: colors.accent,
                  opacity: !urlInput.startsWith('http') || isUrlSubmitting ? 0.5 : 1,
                }]}
                onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled }); handleUrlSubmit(); }}
                disabled={!urlInput.startsWith('http') || isUrlSubmitting}
                accessibilityLabel="Import from URL"
                accessibilityRole="button"
              >
                {isUrlSubmitting ? (
                  <ActivityIndicator size="small" color={colors.card} />
                ) : (
                  <>
                    <Ionicons name="download-outline" size={18} color={colors.card} />
                    <Text style={[styles.primaryButtonText, { color: colors.card }]}>Import</Text>
                  </>
                )}
              </AnimatedPressable>
            </View>
            <View style={[styles.urlExamplesCard, { backgroundColor: colors.card }]}>
              <Text style={[styles.urlExamplesTitle, { color: colors.muted }]}>Supported sites</Text>
              <Text style={[styles.urlExamplesText, { color: colors.muted }]}>
                eBay, Mercari, StockX, TCGPlayer, BrickLink, MyFigureCollection, Ktown4u, Weverse
              </Text>
            </View>
          </View>
        </KeyboardAvoidingView>
      )}

      {scanState === 'scanning' && inputMode === 'camera' && (
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
                <AnimatedPressable
                  style={[styles.manualSubmitButton, {
                    backgroundColor: colors.accent,
                    opacity: manualIsbn.length < 10 || isManualSubmitting ? 0.5 : 1
                  }]}
                  onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled }); handleManualSubmit(); }}
                  disabled={manualIsbn.length < 10 || isManualSubmitting}
                  accessibilityLabel="Look up ISBN"
                  accessibilityRole="button"
                >
                  {isManualSubmitting ? (
                    <ActivityIndicator size="small" color={colors.card} />
                  ) : (
                    <Ionicons name="search" size={20} color={colors.card} />
                  )}
                </AnimatedPressable>
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
                  {intakeResult ? ` (${Math.round(intakeResult.category_confidence * 100)}% confidence)` : ''}
                </Text>
              </View>
            )}

            {intakeResult?.identification_method && (
              <View style={styles.productMeta}>
                <Ionicons name="bulb-outline" size={16} color={colors.muted} />
                <Text style={[styles.productMetaText, { color: colors.muted }]}>
                  Identified via: {intakeResult.identification_method.replace(/_/g, ' ')}
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
                  {formatPrice(lookupResult.priceBand.q50, settings.currency)}
                </Text>
                <Text style={[styles.priceRange, { color: colors.muted }]}>
                  Range: {formatPrice(lookupResult.priceBand.q10, settings.currency)} – {formatPrice(lookupResult.priceBand.q90, settings.currency)}
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
            <AnimatedPressable
              style={[styles.secondaryButtonHalf, { borderColor: colors.border }]}
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); handleRescan(); }}
              accessibilityRole="button"
              accessibilityLabel="Scan another barcode"
            >
              <Ionicons name="scan-outline" size={18} color={colors.text} />
              <Text style={[styles.secondaryButtonText, { color: colors.text }]}>Scan Another</Text>
            </AnimatedPressable>

            <AnimatedPressable
              style={[styles.primaryButtonHalf, { backgroundColor: colors.accent, opacity: isSaving ? 0.7 : 1 }]}
              onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled }); handleSaveToCollection(); }}
              disabled={isSaving}
              accessibilityRole="button"
              accessibilityLabel="Save to collection"
            >
              {isSaving ? (
                <ActivityIndicator size="small" color={colors.card} />
              ) : (
                <>
                  <Ionicons name="add-circle-outline" size={18} color={colors.card} />
                  <Text style={[styles.primaryButtonText, { color: colors.card }]}>Save</Text>
                </>
              )}
            </AnimatedPressable>
          </View>

          <AnimatedPressable
            style={[styles.watchlistButton, { borderColor: colors.border }]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); handleAddToWatchlist(); }}
            accessibilityRole="button"
            accessibilityLabel="Add to watchlist instead"
          >
            <Ionicons name="eye-outline" size={18} color={colors.muted} />
            <Text style={[styles.watchlistButtonText, { color: colors.muted }]}>Add to Watchlist Instead</Text>
          </AnimatedPressable>

          {affiliateLink && (
            <AnimatedPressable
              style={[styles.watchlistButton, { borderColor: colors.border, marginTop: 8 }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                Linking.openURL(affiliateLink.url).catch(() => {});
              }}
              accessibilityRole="link"
              accessibilityLabel={affiliateLink.label}
            >
              <Ionicons name="open-outline" size={18} color={colors.accent} />
              <Text style={[styles.watchlistButtonText, { color: colors.accent }]}>{affiliateLink.label}</Text>
            </AnimatedPressable>
          )}
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
    </SafeAreaView>
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
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
  },
  permissionButtonText: {
    fontSize: 17,
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
    paddingVertical: 16,
    borderRadius: 12,
  },
  primaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
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
  secondaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  secondaryButtonText: {
    fontSize: 16,
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
modeToggleRow: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  modeToggleButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
  },
  modeToggleText: {
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
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
    width: 56,
    height: 56,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
