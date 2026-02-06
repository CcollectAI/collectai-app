import React from "react";
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

type ImportSummary = {
  total: number;
  inserted: number;
  skipped: number;
  error?: string;
  errors?: { row: number; message: string }[];
};

type Props = {
  importBusy: boolean;
  importSummary: ImportSummary | null;
  onUploadFile: () => void;
  onDownloadTemplate: () => void;
};

export const AddImportCard: React.FC<Props> = ({
  importBusy,
  importSummary,
  onUploadFile,
  onDownloadTemplate,
}) => {
  // Local static theme so we don't depend on useAppTheme
  const theme = {
    colors: {
      card: "#FFFFFF",
      text: "#1A202C",
      muted: "#4A5568",
      primary: "#02B5C4",
      border: "#E2E8F0",
      background: "#F7FAFC",
    },
  };

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: theme.colors.card,
        },
      ]}
    >
      <Text
        style={[
          styles.title,
          {
            color: theme.colors.text,
          },
        ]}
      >
        Import from file
      </Text>

      <Text
        style={[
          styles.subtitle,
          {
            color: theme.colors.muted,
          },
        ]}
      >
        Already have your collection in a spreadsheet? Upload an Excel or CSV
        file to import items in bulk.
      </Text>

      <View style={styles.buttonRow}>
        <AnimatedPressable
          onPress={importBusy ? undefined : () => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            onUploadFile();
          }}
          style={[
            styles.primaryButton,
            {
              backgroundColor: importBusy ? "#9ADFE6" : theme.colors.primary,
              opacity: importBusy ? 0.7 : 1,
            },
          ]}
        >
          {importBusy && <ActivityIndicator size="small" color="#FFFFFF" />}
          <Text style={styles.primaryButtonText}>
            {importBusy ? "Uploading & parsing…" : "Upload file"}
          </Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            onDownloadTemplate();
          }}
          style={[
            styles.secondaryButton,
            {
              borderColor: theme.colors.border,
              backgroundColor: theme.colors.background,
            },
          ]}
        >
          <Text
            style={[
              styles.secondaryButtonText,
              {
                color: theme.colors.primary,
              },
            ]}
          >
            Download template
          </Text>
        </AnimatedPressable>
      </View>

      {importSummary && (
        <View style={styles.summary}>
          <Text
            style={[
              styles.summaryText,
              {
                color: theme.colors.muted,
              },
            ]}
          >
            Imported {importSummary.inserted} of {importSummary.total} rows
            {importSummary.skipped > 0
              ? ` · ${importSummary.skipped} skipped`
              : ""}
          </Text>

          {!!importSummary.error && (
            <Text style={styles.errorText}>{importSummary.error}</Text>
          )}

          {Array.isArray(importSummary.errors) &&
            importSummary.errors.length > 0 && (
              <View style={styles.errorList}>
                {importSummary.errors.slice(0, 3).map((err, idx) => (
                  <Text key={idx} style={styles.errorItem}>
                    Row {err.row}: {err.message}
                  </Text>
                ))}
                {importSummary.errors.length > 3 && (
                  <Text style={styles.moreErrorsText}>
                    + {importSummary.errors.length - 3} more issues
                  </Text>
                )}
              </View>
            )}
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    shadowColor: "#000000",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    marginBottom: 12,
    lineHeight: 18,
  },
  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
    columnGap: 8,
    marginBottom: 4,
  },
  primaryButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 999,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "600",
    fontSize: 14,
    marginLeft: 6,
  },
  secondaryButton: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
  },
  secondaryButtonText: {
    fontWeight: "500",
    fontSize: 13,
  },
  summary: {
    marginTop: 10,
  },
  summaryText: {
    fontSize: 13,
  },
  errorText: {
    marginTop: 4,
    fontSize: 12,
    color: "#C53030",
  },
  errorList: {
    marginTop: 4,
  },
  errorItem: {
    fontSize: 11,
    color: "#C53030",
  },
  moreErrorsText: {
    marginTop: 2,
    fontSize: 11,
    color: "#4A5568",
  },
});
