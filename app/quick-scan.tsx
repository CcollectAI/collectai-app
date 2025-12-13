import React, { useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
type DetectedItem = {
  id: string;
  name: string;
  category: string;
  confidence: number;
  estValue: number;
  status: "New" | "Saved";
};

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

const INITIAL_DETECTIONS: DetectedItem[] = [
  {
    id: "d1",
    name: "Charizard GX (Alt Art)",
    category: "Pokémon",
    confidence: 0.94,
    estValue: 420,
    status: "New",
  },
  {
    id: "d2",
    name: "Funko Pop – Luffy (NYCC)",
    category: "Funko Pop",
    confidence: 0.88,
    estValue: 190,
    status: "New",
  },
  {
    id: "d3",
    name: "Hot Wheels RLC Skyline",
    category: "Diecast",
    confidence: 0.91,
    estValue: 160,
    status: "New",
  },
];

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(value);

const QuickScanScreen: React.FC = () => {
  const colors = useAppColors();
  const [items, setItems] = useState<DetectedItem[]>(INITIAL_DETECTIONS);

  const saveItem = (id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, status: "Saved" } : item
      )
    );
  };

  const savedCount = items.filter((i) => i.status === "Saved").length;

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>
              QuickScan (mock)
            </Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>
              This simulates a scan result: detected items with confidence and
              estimated value.
            </Text>
          </View>
          <View style={styles.headerIconCircle}>
            <Ionicons
              name="scan-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Banner */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.bannerRow}>
            <Ionicons
              name="camera-outline"
              size={18}
              color={colors.accent}
            />
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Text style={[styles.bannerTitle, { color: colors.text }]}>
                Camera flow coming later
              </Text>
              <Text style={[styles.bannerText, { color: colors.muted }]}>
                For now, this view only mocks what happens after a photo or
                screenshot is analysed.
              </Text>
            </View>
          </View>
        </View>

        {/* Summary */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.summaryRow}>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Detected
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {items.length}
              </Text>
            </View>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Saved (mock)
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {savedCount}
              </Text>
            </View>
          </View>
          <Text style={[styles.summaryHint, { color: colors.muted }]}>
            Later this will push directly into your portfolio and watchlist
            via Supabase.
          </Text>
        </View>

        {/* Detected items */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: colors.card,
              borderColor: colors.border,
              marginBottom: 24,
            },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Detected items
            </Text>
            <Text style={[styles.cardMeta, { color: colors.muted }]}>
              Tap &quot;Save (mock)&quot; to mark as added.
            </Text>
          </View>

          {items.map((item, idx) => {
            const isSaved = item.status === "Saved";

            return (
              <View key={item.id}>
                <View style={styles.itemRow}>
                  <View style={styles.itemMain}>
                    <Text
                      style={[
                        styles.itemName,
                        { color: colors.text },
                      ]}
                      numberOfLines={1}
                    >
                      {item.name}
                    </Text>
                    <Text
                      style={[
                        styles.itemMeta,
                        { color: colors.muted },
                      ]}
                    >
                      {item.category} · Confidence{" "}
                      {(item.confidence * 100).toFixed(0)}%
                    </Text>
                    <Text
                      style={[
                        styles.itemMeta,
                        { color: colors.muted },
                      ]}
                    >
                      Est. value {formatCurrency(item.estValue)}
                    </Text>
                  </View>

                  <View style={styles.itemRight}>
                    <Pressable
                      disabled={isSaved}
                      onPress={() => saveItem(item.id)}
                      style={[
                        styles.saveButton,
                        {
                          backgroundColor: isSaved
                            ? "rgba(11,168,108,0.12)"
                            : colors.accent,
                        },
                      ]}
                    >
                      <Text
                        style={[
                          styles.saveButtonText,
                          { color: isSaved ? "#0BA86C" : "#FFFFFF" },
                        ]}
                      >
                        {isSaved ? "Saved" : "Save (mock)"}
                      </Text>
                    </Pressable>
                  </View>
                </View>

                {idx < items.length - 1 && (
                  <View
                    style={[
                      styles.separator,
                      { backgroundColor: colors.border },
                    ]}
                  />
                )}
              </View>
            );
          })}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 13,
    marginTop: 4,
  },
  headerIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F3F6F8",
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  bannerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  bannerTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  bannerText: {
    fontSize: 12,
    marginTop: 2,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  summaryBlock: {
    flex: 1,
    marginRight: 8,
  },
  summaryLabel: {
    fontSize: 11,
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: "600",
    marginTop: 2,
  },
  summaryHint: {
    fontSize: 11,
    marginTop: 6,
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginBottom: 6,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: "600",
  },
  cardMeta: {
    fontSize: 11,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 6,
  },
  itemMain: {
    flex: 1,
    marginRight: 8,
  },
  itemName: {
    fontSize: 14,
    fontWeight: "600",
  },
  itemMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
  },
  saveButton: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  saveButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
});

export default QuickScanScreen;
