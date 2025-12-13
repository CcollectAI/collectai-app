#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

ADD_FILE="app/(tabs)/add.tsx"
ADD_BAK="${ADD_FILE}.bak_quickscan_fraud_$(date +%Y%m%d-%H%M%S)"

if [ -f "$ADD_FILE" ]; then
  cp "$ADD_FILE" "$ADD_BAK"
  echo "📦 Backed up existing Add screen to:"
  echo "  $ADD_BAK"
else
  echo "⚠️  $ADD_FILE not found. Creating a new one."
fi

cat > "$ADD_FILE" <<'TSX'
import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

/**
 * Add screen:
 * - SafeAreaView to avoid notch bleed
 * - QuickScan hero is the main action
 * - Fraud / security checks card (informational)
 * - Manual add as a secondary path
 *
 * NOTE:
 *  - Wire `handleQuickScanPress` and `handleManualAddPress`
 *    to your real navigation/flows.
 */

const AddScreen: React.FC = () => {
  const handleQuickScanPress = () => {
    // TODO: replace with your real QuickScan trigger
    // Example:
    // router.push("/quickscan-advanced");
    console.log("QuickScan pressed");
  };

  const handleManualAddPress = () => {
    // TODO: replace with your real manual-add navigation
    // Example:
    // router.push("/add-manual");
    console.log("Manual add pressed");
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={styles.title}>Add to your collection</Text>
          <Text style={styles.subtitle}>Fast, camera-first flow.</Text>
        </View>

        {/* QuickScan hero card */}
        <TouchableOpacity
          style={styles.quickScanCard}
          activeOpacity={0.9}
          onPress={handleQuickScanPress}
        >
          <View style={styles.quickScanIconCircle}>
            <Ionicons name="scan-outline" size={32} />
          </View>
          <Text style={styles.quickScanTitle}>QuickScan (beta)</Text>
          <Text style={styles.quickScanSubtitle}>
            Snap a photo and we prefill the details. You can override anything
            before saving.
          </Text>
          <View style={styles.quickScanButton}>
            <Text style={styles.quickScanButtonText}>Start QuickScan</Text>
            <Ionicons name="chevron-forward" size={18} />
          </View>
        </TouchableOpacity>

        {/* Fraud & security checks card */}
        <View style={styles.fraudCard}>
          <View style={styles.fraudHeaderRow}>
            <View style={styles.fraudIconCircle}>
              <Ionicons name="shield-checkmark-outline" size={20} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.fraudTitle}>Risk & fraud checks</Text>
              <Text style={styles.fraudSubtitle}>
                We run background checks on pricing, listings, and patterns to
                highlight potential risk signals in your collection.
              </Text>
            </View>
          </View>

          <View style={styles.fraudBulletRow}>
            <View style={styles.bulletDot} />
            <Text style={styles.fraudBulletText}>
              Flags suspicious price spikes or under-market listings
            </Text>
          </View>
          <View style={styles.fraudBulletRow}>
            <View style={styles.bulletDot} />
            <Text style={styles.fraudBulletText}>
              Highlights items often targeted by counterfeiters
            </Text>
          </View>
          <View style={styles.fraudBulletRow}>
            <View style={styles.bulletDot} />
            <Text style={styles.fraudBulletText}>
              Surfaces items worth extra provenance (grading, receipts, photos)
            </Text>
          </View>

          <Text style={styles.fraudFooterText}>
            Fraud checks run in the background after you add items. You&apos;ll
            see risk hints on item detail and alerts in your watchlist.
          </Text>
        </View>

        {/* Divider */}
        <View style={styles.dividerRow}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>or</Text>
          <View style={styles.dividerLine} />
        </View>

        {/* Manual add card (secondary) */}
        <TouchableOpacity
          style={styles.manualCard}
          activeOpacity={0.9}
          onPress={handleManualAddPress}
        >
          <View style={styles.manualIconCircle}>
            <Ionicons name="create-outline" size={24} />
          </View>
          <View style={styles.manualTextBlock}>
            <Text style={styles.manualTitle}>Add manually</Text>
            <Text style={styles.manualSubtitle}>
              Enter card / figure details yourself if you prefer full control.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} />
        </TouchableOpacity>
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
  fraudCard: {
    borderRadius: 14,
    padding: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E0E7EC",
    marginBottom: 20,
  },
  fraudHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 8,
    gap: 8,
  },
  fraudIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#E6F7FF",
  },
  fraudTitle: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 2,
  },
  fraudSubtitle: {
    fontSize: 12,
    opacity: 0.8,
  },
  fraudBulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginTop: 6,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#00A3C4",
    marginTop: 4,
    marginRight: 8,
  },
  fraudBulletText: {
    fontSize: 12,
    opacity: 0.85,
    flex: 1,
  },
  fraudFooterText: {
    fontSize: 11,
    opacity: 0.7,
    marginTop: 10,
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
TSX

echo "✅ Overwrote $ADD_FILE with SafeArea + QuickScan + Fraud card version."
