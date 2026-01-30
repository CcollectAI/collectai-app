import { Alert, Linking } from 'react-native';
import { router } from 'expo-router';
import { AddImportCard } from '@/components/AddImportCard';
import { AddQuickScanLayoutPro } from '@/components/AddQuickScanLayoutPro';
const API_BASE_URL_IMPORT = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8080';

const IMPORT_TEMPLATE_URL = process.env.EXPO_PUBLIC_IMPORT_TEMPLATE_URL ?? null;
import * as DocumentPicker from 'expo-document-picker';
import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";

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

  const handleQuickScanPress = () => {
    router.push('/quickscan');
  };

  const handleManualAddPress = () => {
    // TODO: replace with your real manual-add navigation
    // Example:
    // router.push("/add-manual");
    console.log("Manual add pressed");
  };

  

  const [importSummary, setImportSummary] = React.useState<any>(null);
  const [importBusy, setImportBusy] = React.useState(false);

  

  


  const handleDownloadImportTemplate = () => {
    if (!IMPORT_TEMPLATE_URL) {
      Alert.alert(
        "Template not configured",
        "Ask your developer to set EXPO_PUBLIC_IMPORT_TEMPLATE_URL so this button can open the latest import template."
      );
      return;
    }

    Linking.openURL(IMPORT_TEMPLATE_URL).catch((err) => {
      console.error("[Add] Failed to open template URL", err);
      Alert.alert(
        "Could not open template",
        "We couldn't open the template link. Please try again later."
      );
    });
  };

const handleImportCollectionFile = async () => {
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

      if (!result) {
      return;
    }

    // Handle both new (assets) and old (single object) shapes from DocumentPicker
    // @ts-ignore
    const canceled = result.canceled ?? (result.type && result.type !== 'success');
    if (canceled) {
      return;
    }

    // @ts-ignore
    const asset = result.assets && result.assets.length > 0 ? result.assets[0] : result;

    // Basic safety checks
    // @ts-ignore
    if (!asset || !asset.uri) {
      console.warn('[Add] import: no asset URI found', asset);
      return;
    }

    try {
      setImportBusy(true);
      setImportSummary(null);

      const formData = new FormData();
      formData.append("file", {
        // @ts-ignore
        uri: asset.uri,
        // @ts-ignore
        name: asset.name || "collection.xlsx",
        // @ts-ignore
        type: asset.mimeType || "application/octet-stream",
      } as any);

      const res = await fetch(`${API_BASE_URL_IMPORT}/api/imports/collection`, {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
        body: formData,
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("[Add] import error response", res.status, text);
        setImportSummary({
          total: 0,
          inserted: 0,
          skipped: 0,
          error: text || "Import failed",
        });
        return;
      }

      const json = await res.json();
      console.log("[Add] import summary", json);
      setImportSummary({
        total: json.total_rows ?? 0,
        inserted: json.inserted_count ?? 0,
        skipped: json.skipped_count ?? 0,
        errors: json.errors ?? [],
      });
    } finally {
      setImportBusy(false);
    }
      // TODO: wire to backend /api/imports/collection in next step
    } catch (e) {
      console.error('[Add] import collection file error', e);
    }
  };


  
return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.container}>
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={[styles.title, { color: colors.text }]}>Add to your collection</Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>Fast, camera-first flow.</Text>
        </View>

        {/* QuickScan hero card */}
        <TouchableOpacity
          style={[styles.quickScanCard, { backgroundColor: colors.card }]}
          activeOpacity={0.9}
          onPress={handleQuickScanPress}
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
        </TouchableOpacity>

        {/* Divider */}
        <View style={styles.dividerRow}>
          <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
          <Text style={[styles.dividerText, { color: colors.muted }]}>or</Text>
          <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
        </View>

        {/* Manual add card (secondary) */}
        <TouchableOpacity
          style={[styles.manualCard, { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 }]}
          activeOpacity={0.9}
          onPress={handleManualAddPress}
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
        </TouchableOpacity>

        <AddImportCard
          importBusy={importBusy}
          importSummary={importSummary}
          onUploadFile={handleImportCollectionFile}
          onDownloadTemplate={handleDownloadImportTemplate}
        />

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
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 14,
    opacity: 0.7,
    marginTop: 4,
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
    marginBottom: 16,
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
});

export default AddScreen;
