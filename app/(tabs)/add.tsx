import {
  Linking,
  Platform,
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
} from 'react-native';
// expo-file-system v19 moved the legacy API (cacheDirectory, downloadAsync)
// to a `/legacy` submodule. The v19 default export uses a new `File`-based
// class API. Sticking with legacy here keeps the existing pattern simple
// and matches what other Sparrow Collect helpers use.
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { router } from 'expo-router';
import { AddImportCard } from '@/components/AddImportCard';
import { API_BASE } from '@/api/config';
import { pickDocument } from '@/lib/documentPicker';
import React from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useTranslation } from "react-i18next";
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';

/**
 * Add screen:
 * - SafeAreaView to avoid notch bleed
 * - QuickScan hero is the main action
 * - Manual add as a secondary path
 *
 * NOTE:
 *  - Wire `handleQuickScanPress` and `handleManualAddPress`
 *    to your real navigation/flows.
 */

const AddScreen: React.FC = () => {
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { showToast } = useToast();

  const handleQuickScanPress = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/quickscan');
  };

  const handleManualAddPress = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push("/add-manual");
  };

  

  const [importSummary, setImportSummary] = React.useState<{
    total: number;
    inserted: number;
    skipped: number;
    error?: string;
    errors?: { row: number; message: string }[];
  } | null>(null);
  const [importBusy, setImportBusy] = React.useState(false);

  

  


  const handleDownloadImportTemplate = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const templateUrl = `${API_BASE}/api/imports/template`;

    // On web, Linking.openURL triggers a real browser download.
    // On iOS/Android, mobile browsers display CSV inline as text rather
    // than downloading — that was the original bug. Download to a temp
    // file then open the OS share sheet so the user can save to Files /
    // email it / send to AirDrop.
    if (Platform.OS === 'web') {
      Linking.openURL(templateUrl).catch((err) => {
        logger.error('[Add] Failed to open template URL', err);
        showToast({ message: 'Could not open template. Please try again later.', type: 'error' });
      });
      return;
    }

    try {
      const dest = `${FileSystem.cacheDirectory}collectai_import_template.csv`;
      const { uri, status } = await FileSystem.downloadAsync(templateUrl, dest);
      if (status !== 200) {
        throw new Error(`HTTP ${status}`);
      }
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, {
          mimeType: 'text/csv',
          dialogTitle: 'Save Sparrow Collect import template',
          UTI: 'public.comma-separated-values-text',
        });
      } else {
        // Sharing unavailable (rare on mobile) — show the file path in the
        // toast so power users can find it manually.
        showToast({ message: `Template saved to ${uri}`, type: 'success' });
      }
    } catch (err) {
      logger.error('[Add] Failed to download import template', err);
      showToast({
        message: 'Could not download template. Check your connection and try again.',
        type: 'error',
      });
    }
  };

const handleImportCollectionFile = async () => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      const pickResult = await pickDocument([
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ]);

      if (pickResult.canceled || !pickResult.document) {
        return;
      }

      const { uri, name, mimeType } = pickResult.document;

    try {
      setImportBusy(true);
      setImportSummary(null);

      const formData = new FormData();
      // React Native's FormData accepts this shape for file uploads
      formData.append("file", {
        uri,
        name,
        type: mimeType,
      } as unknown as Blob);

      const res = await fetch(`${API_BASE}/api/imports/collection`, {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
        body: formData,
      });

      if (!res.ok) {
        const text = await res.text();
        logger.error("[Add] import error response", res.status, text);
        setImportSummary({
          total: 0,
          inserted: 0,
          skipped: 0,
          error: text || "Import failed",
        });
        return;
      }

      const json = await res.json();
      logger.info("[Add] import summary", json);
      setImportSummary({
        total: json.total_rows ?? 0,
        inserted: json.inserted_count ?? 0,
        skipped: json.skipped_count ?? 0,
        errors: json.errors ?? [],
      });
    } finally {
      setImportBusy(false);
    }
    } catch (e) {
      logger.error('[Add] import collection file error', e);
    }
  };


  
return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.title, { color: colors.text }]}>Add</Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>{t('add_tab.subtitle')}</Text>
          </View>
          <View style={styles.headerIcons}>
            <InboxHeaderButton color={colors.text} size={22} />
            <ThemeToggleButton size={22} />
          </View>
        </View>

        {/* QuickScan hero card with backdrop */}
        <View style={[styles.quickScanBackdrop, { backgroundColor: colors.quickscanBackdrop }]}>
          <AnimatedPressable
            style={[styles.quickScanCard, { backgroundColor: colors.card }]}
            onPress={handleQuickScanPress}
            accessibilityRole="button"
            accessibilityLabel={t('add_tab.start_quickscan_a11y')}
          >
            <View style={[styles.quickScanIconCircle, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name="scan-outline" size={32} color={colors.accent} />
            </View>
            <Text style={[styles.quickScanTitle, { color: colors.text }]}>{t('add_tab.quickscan_ai')}</Text>
            <Text style={[styles.quickScanSubtitle, { color: colors.muted }]}>
              Snap a photo and we prefill the details. You can override anything
              before saving.
            </Text>
            <View style={[styles.quickScanButton, { backgroundColor: colors.accent + '20' }]}>
              <Text style={[styles.quickScanButtonText, { color: colors.accent }]}>{t('add_tab.start_quickscan')}</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.accent} />
            </View>
          </AnimatedPressable>
        </View>

        {/* Barcode / ISBN scan card */}
        <AnimatedPressable
          style={[styles.barcodeCard, { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/barcode-scan');
          }}
          accessibilityRole="button"
          accessibilityLabel={t('add_tab.scan_barcode_a11y')}
        >
          <View style={[styles.barcodeIconCircle, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="barcode-outline" size={24} color={colors.accent} />
          </View>
          <View style={styles.barcodeTextBlock}>
            <Text style={[styles.barcodeTitle, { color: colors.text }]}>{t('add_tab.scan_barcode')}</Text>
            <Text style={[styles.barcodeSubtitle, { color: colors.muted }]}>
              Books, albums, boxed products with barcodes.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>

        {/* Import from file (replaces the former URL-import card 2026-04-18) */}
        <AddImportCard
          importBusy={importBusy}
          importSummary={importSummary}
          onUploadFile={handleImportCollectionFile}
          onDownloadTemplate={handleDownloadImportTemplate}
        />

        {/* Divider */}
        <View style={styles.dividerRow}>
          <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
          <Text style={[styles.dividerText, { color: colors.muted }]}>or</Text>
          <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
        </View>

        {/* Manual add card (secondary) */}
        <AnimatedPressable
          style={[styles.manualCard, { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 }]}
          onPress={handleManualAddPress}
          accessibilityRole="button"
          accessibilityLabel={t('add_tab.add_manually_a11y')}
        >
          <View style={[styles.manualIconCircle, { backgroundColor: colors.background }]}>
            <Ionicons name="create-outline" size={24} color={colors.text} />
          </View>
          <View style={styles.manualTextBlock}>
            <Text style={[styles.manualTitle, { color: colors.text }]}>{t('add_tab.add_manually')}</Text>
            <Text style={[styles.manualSubtitle, { color: colors.muted }]}>
              Enter card / figure details yourself if you prefer full control.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>
        </Animated.View>
</ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  container: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerIcons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  quickScanBackdrop: {
    marginHorizontal: -16,
    paddingHorizontal: 16,
    paddingVertical: 16,
    marginBottom: 16,
    borderRadius: 20,
  },
  quickScanCard: {
    borderRadius: 16,
    padding: 20,
    elevation: 2, // Android
    shadowColor: "#000", // iOS shadow
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  quickScanIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },
  quickScanTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 6,
  },
  quickScanSubtitle: {
    fontSize: 14,
    marginBottom: 16,
  },
  quickScanButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  quickScanButtonText: {
    fontSize: 14,
    fontWeight: "600",
    marginRight: 4,
  },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    marginHorizontal: 8,
    fontSize: 12,
  },
  manualCard: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  manualIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  manualTextBlock: {
    flex: 1,
  },
  manualTitle: {
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 2,
  },
  manualSubtitle: {
    fontSize: 13,
  },
  barcodeCard: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    gap: 10,
  },
  barcodeIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: "center",
    alignItems: "center",
  },
  barcodeTextBlock: {
    flex: 1,
  },
  barcodeTitle: {
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 2,
  },
  barcodeSubtitle: {
    fontSize: 13,
  },
});

function AddScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Add">
      <AddScreen />
    </ScreenErrorBoundary>
  );
}

export default AddScreenWithBoundary;
