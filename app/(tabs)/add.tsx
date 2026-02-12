import { Alert, Linking } from 'react-native';
import { router } from 'expo-router';
import { AddImportCard } from '@/components/AddImportCard';
import { API_BASE } from '@/api/config';
import * as DocumentPicker from 'expo-document-picker';
import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
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

  

  


  const handleDownloadImportTemplate = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const templateUrl = `${API_BASE}/api/imports/template`;
    Linking.openURL(templateUrl).catch((err) => {
      logger.error("[Add] Failed to open template URL", err);
      Alert.alert(
        "Could not open template",
        "We couldn't open the template link. Please try again later."
      );
    });
  };

const handleImportCollectionFile = async () => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          'text/csv',
          'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ],
        copyToCacheDirectory: true,
      });

      // NOTE: return shape differs slightly by Expo SDK; for now just log it.
      if (!result) {
        return;
      }

    // Handle both new (assets) and old (single object) shapes from DocumentPicker
    // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
    const canceled = result.canceled ?? (result.type && result.type !== 'success');
    if (canceled) {
      return;
    }

    // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
    const asset = result.assets && result.assets.length > 0 ? result.assets[0] : result;

    // Basic safety checks
    // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
    if (!asset || !asset.uri) {
      logger.warn('[Add] import: no asset URI found', asset);
      return;
    }

    try {
      setImportBusy(true);
      setImportSummary(null);

      const formData = new FormData();
      // React Native's FormData accepts this shape for file uploads
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formData.append("file", {
        // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
        uri: asset.uri,
        // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
        name: asset.name || "collection.xlsx",
        // @ts-expect-error – DocumentPicker asset shape varies by Expo SDK version
        type: asset.mimeType || "application/octet-stream",
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
            <Text style={[styles.subtitle, { color: colors.muted }]}>Fast, camera-first flow.</Text>
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
            accessibilityLabel="Start QuickScan to add item by photo"
          >
            <View style={[styles.quickScanIconCircle, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name="scan-outline" size={32} color={colors.accent} />
            </View>
            <Text style={[styles.quickScanTitle, { color: colors.text }]}>QuickScan (beta)</Text>
            <Text style={[styles.quickScanSubtitle, { color: colors.muted }]}>
              Snap a photo and we prefill the details. You can override anything
              before saving.
            </Text>
            <View style={[styles.quickScanButton, { backgroundColor: colors.accent + '20' }]}>
              <Text style={[styles.quickScanButtonText, { color: colors.accent }]}>Start QuickScan</Text>
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
          accessibilityLabel="Scan barcode or ISBN"
        >
          <View style={[styles.barcodeIconCircle, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="barcode-outline" size={24} color={colors.accent} />
          </View>
          <View style={styles.barcodeTextBlock}>
            <Text style={[styles.barcodeTitle, { color: colors.text }]}>Scan barcode / ISBN</Text>
            <Text style={[styles.barcodeSubtitle, { color: colors.muted }]}>
              Books, albums, boxed products with barcodes.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>

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
          accessibilityLabel="Add item manually"
        >
          <View style={[styles.manualIconCircle, { backgroundColor: colors.background }]}>
            <Ionicons name="create-outline" size={24} color={colors.text} />
          </View>
          <View style={styles.manualTextBlock}>
            <Text style={[styles.manualTitle, { color: colors.text }]}>Add manually</Text>
            <Text style={[styles.manualSubtitle, { color: colors.muted }]}>
              Enter card / figure details yourself if you prefer full control.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>

        <AddImportCard
          importBusy={importBusy}
          importSummary={importSummary}
          onUploadFile={handleImportCollectionFile}
          onDownloadTemplate={handleDownloadImportTemplate}
        />
        </Animated.View>
</ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F5F7FA",
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
    backgroundColor: "#FFFFFF",
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
    backgroundColor: "#E6F7FF",
  },
  quickScanTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 6,
  },
  quickScanSubtitle: {
    fontSize: 14,
    opacity: 0.75,
    marginBottom: 16,
  },
  quickScanButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#D0F0FF",
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
    backgroundColor: "#DDD",
  },
  dividerText: {
    marginHorizontal: 8,
    fontSize: 12,
    opacity: 0.7,
  },
  manualCard: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    padding: 14,
    backgroundColor: "#F5F5F5",
    gap: 10,
  },
  manualIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
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
    opacity: 0.75,
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
    opacity: 0.75,
  },
});

export default AddScreen;
