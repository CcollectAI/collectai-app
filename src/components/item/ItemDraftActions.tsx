/**
 * ItemDraftActions — Save to Collection / Scan Another buttons for draft mode.
 */
import React from 'react';
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';

interface ItemDraftActionsProps {
  savingDraft: boolean;
  saveError: string | null;
  onSaveDraft: () => void;
}

export const ItemDraftActions = React.memo(function ItemDraftActions({ savingDraft, saveError, onSaveDraft }: ItemDraftActionsProps) {
  const { colors: theme } = useAppTheme();
  const router = useRouter();

  return (
    <View style={styles.draftSection}>
      {saveError && (
        <Text style={[styles.errorText, { color: theme.danger }]}>
          {saveError}
        </Text>
      )}

      <View style={styles.draftButtonsRow}>
        <Pressable
          onPress={() => router.push('/quickscan')}
          style={[
            styles.scanAnotherButton,
            { backgroundColor: theme.card, borderColor: theme.border, borderWidth: 1 },
          ]}
          accessibilityRole="button"
          accessibilityLabel="Scan another item"
        >
          <Ionicons name="camera" size={18} color={theme.text} />
          <Text style={[styles.scanAnotherButtonText, { color: theme.text }]}>Scan Another</Text>
        </Pressable>

        <Pressable
          onPress={onSaveDraft}
          disabled={savingDraft}
          style={[
            styles.saveDraftButton,
            { backgroundColor: theme.accent, opacity: savingDraft ? 0.7 : 1 },
          ]}
          accessibilityRole="button"
          accessibilityLabel="Save to collection"
        >
          {savingDraft ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <>
              <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" />
              <Text style={styles.saveDraftButtonText}>Save to Collection</Text>
            </>
          )}
        </Pressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  draftSection: {
    marginBottom: 16,
    gap: 8,
  },
  draftButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  saveDraftButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  saveDraftButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  scanAnotherButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  scanAnotherButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    fontSize: 12,
    textAlign: 'center',
  },
});
