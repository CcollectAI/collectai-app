/**
 * Camera permission screen, shared by QuickScan and the barcode scanner.
 * Shows when camera access has not been granted.
 *
 * iOS only presents a permission dialog ONCE per install. After the user taps
 * "Don't Allow", `requestPermission()` resolves immediately with
 * `granted: false, canAskAgain: false` and no dialog ever appears again — so a
 * button that only calls `requestPermission()` is dead from that point on. When
 * `canAskAgain` is false the only route back is Settings.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Linking,
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
  /**
   * `false` once the OS has permanently denied the prompt. Read straight off
   * the expo permission response — do not default it to `true`, or the blocked
   * state renders a button that silently does nothing.
   */
  canAskAgain: boolean;
  /** Why this screen needs the camera. Varies by caller. */
  message?: string;
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
  canAskAgain,
  message = 'We need camera access to scan your collectibles with AI.',
  colors,
}: PermissionScreenProps) {
  const blocked = !canAskAgain;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.permissionContainer}>
        <Ionicons
          name={blocked ? 'lock-closed-outline' : 'camera-outline'}
          size={64}
          color={colors.muted}
        />
        <Text style={[styles.permissionTitle, { color: colors.text }]}>
          {blocked ? 'Camera Access Is Off' : 'Camera Permission Required'}
        </Text>
        <Text style={[styles.permissionText, { color: colors.muted }]}>
          {blocked
            ? 'Camera access was turned off for Sparrow. Open Settings and switch Camera on to keep scanning.'
            : message}
        </Text>
        <AnimatedPressable
          style={[styles.permissionButton, { backgroundColor: TIFFANY }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            if (blocked) {
              Linking.openSettings();
            } else {
              onGrant();
            }
          }}
          accessibilityRole="button"
          accessibilityLabel={
            blocked ? 'Open Settings to enable camera access' : 'Grant camera permission'
          }
        >
          <Text style={styles.permissionButtonText}>
            {blocked ? 'Open Settings' : 'Grant Permission'}
          </Text>
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
