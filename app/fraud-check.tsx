import React, { useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
type RiskLevel = "Low" | "Medium" | "High" | null;

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

const FraudCheckScreen: React.FC = () => {
  const colors = useAppColors();
  const [url, setUrl] = useState("");
  const [platform, setPlatform] = useState("");
  const [notes, setNotes] = useState("");
  const [risk, setRisk] = useState<RiskLevel>(null);
  const [explanation, setExplanation] = useState<string>("");

  const runCheck = () => {
    // Very simple mock logic: certain keywords give higher risk
    const lower = (url + " " + platform + " " + notes).toLowerCase();
    let newRisk: RiskLevel = "Low";
    let expl =
      "Looks fairly safe based on this very simple mock checker.";

    if (lower.includes("facebook") || lower.includes("marketplace")) {
      newRisk = "Medium";
      expl =
        "Social marketplaces can be fine but often have less buyer protection.";
    }
    if (lower.includes("wire") || lower.includes("crypto")) {
      newRisk = "High";
      expl =
        "High risk: off-platform / irreversible payment mentioned (wire / crypto).";
    }

    setRisk(newRisk);
    setExplanation(expl);
  };

  const riskColors: Record<Exclude<RiskLevel, null>, { bg: string; text: string }> = {
    Low: { bg: "rgba(11,168,108,0.12)", text: "#0BA86C" },
    Medium: { bg: "rgba(25,167,174,0.12)", text: "#19A7AE" },
    High: { bg: "rgba(214,69,69,0.12)", text: "#D64545" },
  };

  const riskBadge = risk ? riskColors[risk] : null;

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>
              Fraud check (mock)
            </Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>
              Paste a marketplace listing link and we&apos;ll return a mock
              risk level. Later this will use real signals and models.
            </Text>
          </View>
          <View style={styles.headerIconCircle}>
            <Ionicons
              name="shield-checkmark-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Form card */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          {/* URL */}
          <Text style={[styles.label, { color: colors.muted }]}>
            Listing URL
          </Text>
          <TextInput
            value={url}
            onChangeText={setUrl}
            placeholder="https://www.example.com/listing/123…"
            placeholderTextColor={colors.muted}
            autoCapitalize="none"
            style={[
              styles.input,
              {
                color: colors.text,
                borderColor: colors.border,
              },
            ]}
          />

          {/* Platform */}
          <Text style={[styles.label, { color: colors.muted }]}>
            Platform / marketplace
          </Text>
          <TextInput
            value={platform}
            onChangeText={setPlatform}
            placeholder="eBay, Vinted, Facebook Marketplace…"
            placeholderTextColor={colors.muted}
            style={[
              styles.input,
              {
                color: colors.text,
                borderColor: colors.border,
              },
            ]}
          />

          {/* Notes */}
          <Text style={[styles.label, { color: colors.muted }]}>
            Extra notes (optional)
          </Text>
          <TextInput
            value={notes}
            onChangeText={setNotes}
            placeholder="Payment method, seller behaviour, anything that feels off…"
            placeholderTextColor={colors.muted}
            multiline
            style={[
              styles.input,
              styles.notesInput,
              {
                color: colors.text,
                borderColor: colors.border,
              },
            ]}
          />

          <Pressable
            onPress={runCheck}
            style={[
              styles.runButton,
              { backgroundColor: colors.accent },
            ]}
          >
            <Text
              style={[styles.runButtonText, { color: "#FFFFFF" }]}
            >
              Run fraud check (mock)
            </Text>
          </Pressable>

          {/* Result */}
          {risk && (
            <View style={styles.resultBox}>
              <View
                style={[
                  styles.riskBadge,
                  {
                    backgroundColor: riskBadge?.bg,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.riskBadgeText,
                    { color: riskBadge?.text },
                  ]}
                >
                  {risk} risk (mock)
                </Text>
              </View>
              <Text
                style={[styles.resultText, { color: colors.muted }]}
              >
                {explanation}
              </Text>

              <Text
                style={[styles.disclaimer, { color: colors.muted }]}
              >
                This checker is just a helper. Always use your own judgement
                and platform protections.
              </Text>
            </View>
          )}
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
  label: {
    fontSize: 12,
    marginTop: 8,
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
  },
  notesInput: {
    minHeight: 80,
    textAlignVertical: "top",
  },
  runButton: {
    marginTop: 14,
    borderRadius: 999,
    paddingVertical: 10,
    alignItems: "center",
  },
  runButtonText: {
    fontSize: 14,
    fontWeight: "600",
  },
  resultBox: {
    marginTop: 14,
  },
  riskBadge: {
    alignSelf: "flex-start",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 6,
  },
  riskBadgeText: {
    fontSize: 11,
    fontWeight: "600",
  },
  resultText: {
    fontSize: 12,
    lineHeight: 17,
  },
  disclaimer: {
    fontSize: 11,
    marginTop: 6,
  },
});

export default FraudCheckScreen;
