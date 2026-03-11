/**
 * Camera permission request screen for QuickScan.
 * Shows when camera access has not been granted.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { BRAND_COLORS } from '@/constants/colors';

const TIFFANY = BRAND_COLORS.tiffany;

interface PermissionScreenProps {
  onGrant: () => void;
  onCancel: () => void;
  hapticsEnabled: boolean;
  colors: {
    background: string;
    text: string;
    muted: string;
  };
}

function PermissionScreenInner({
  onGrant,
  onCancel,
  hapticsEnabled,
  colors,
}: PermissionScreenProps) {
  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.permissionContainer}>
        <Ionicons name="camera-outline" size={64} color={colors.muted} />
        <Text style={[styles.permissionTitle, { color: colors.text }]}>
          Camera Permission Required
        </Text>
        <Text style={[styles.permissionText, { color: colors.muted }]}>
          We need camera access to scan your collectibles with AI.
        </Text>
        <AnimatedPressable
          style={[styles.permissionButton, { backgroundColor: TIFFANY }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            onGrant();
          }}
          accessibilityRole="button"
          accessibilityLabel="Grant camera permission"
        >
          <Text style={styles.permissionButtonText}>Grant Permission</Text>
        </AnimatedPressable>
        <AnimatedPressable
          style={styles.backBtn}
          onPress={onCancel}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Text style={[styles.backBtnText, { color: colors.muted }]}>Go Back</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
}

export const PermissionScreen = React.memo(PermissionScreenInner);

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
    color: '#FFFFFF',
  },
  backBtn: {
    marginTop: 16,
    padding: 8,
  },
  backBtnText: {
    fontSize: 15,
  },
});
