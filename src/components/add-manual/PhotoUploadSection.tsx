import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

interface Props {
  photoUrl: string | null;
  photoUploading: boolean;
  photoError: string | null;
  onShowSourcePicker: () => void;
}

export const PhotoUploadSection = React.memo(function PhotoUploadSection({
  photoUrl,
  photoUploading,
  photoError,
  onShowSourcePicker,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="camera-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Photo (Optional)</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.photoContent}>
          {photoUrl ? (
            <Image source={{ uri: photoUrl }} style={styles.photoPreview} />
          ) : (
            <View style={[styles.photoPlaceholder, { borderColor: colors.border }]}>
              <Ionicons name="camera-outline" size={32} color={colors.muted} />
            </View>
          )}

          {photoUploading ? (
            <View style={styles.photoUploadingRow}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.photoUploadingText, { color: colors.muted }]}>Uploading…</Text>
            </View>
          ) : (
            <AnimatedPressable
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onShowSourcePicker(); }}
              style={[styles.addPhotoBtn, { borderColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel={photoUrl ? "Change photo" : "Add photo"}
            >
              <Ionicons name={photoUrl ? "swap-horizontal-outline" : "camera-outline"} size={16} color={colors.accent} />
              <Text style={[styles.addPhotoBtnText, { color: colors.accent }]}>{photoUrl ? "Change" : "Add Photo"}</Text>
            </AnimatedPressable>
          )}

          {photoError && (
            <Text style={[styles.photoError, { color: colors.danger }]}>{photoError}</Text>
          )}
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: { marginBottom: 20 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  sectionTitle: { fontSize: 14, fontWeight: '600' },
  card: { borderRadius: 12, borderWidth: 1, padding: 14 },
  photoContent: { alignItems: 'center', paddingVertical: 4 },
  photoPreview: { width: 120, height: 120, borderRadius: 12, marginBottom: 12 },
  photoPlaceholder: {
    width: 120, height: 120, borderRadius: 12, borderWidth: 1.5, borderStyle: 'dashed',
    alignItems: 'center', justifyContent: 'center', marginBottom: 12,
  },
  addPhotoBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8, borderWidth: 1,
  },
  addPhotoBtnText: { fontSize: 13, fontWeight: '600' },
  photoUploadingRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  photoUploadingText: { fontSize: 13 },
  photoError: { fontSize: 12, marginTop: 8, textAlign: 'center' },
});
