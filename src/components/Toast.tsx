/**
 * Toast Notification System
 * Slide-in from top, auto-dismiss, color coded, with haptic feedback.
 *
 * Usage:
 *   const { showToast } = useToast();
 *   showToast({ message: 'Item saved', type: 'success' });
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Animated,
  Platform,
  StyleSheet,
  Text,
  Pressable,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { DURATION } from '@/motion/tokens';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';

// --------------- Types ---------------

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastConfig {
  message: string;
  type?: ToastType;
  /** Auto-dismiss duration in ms. Default: 3000. Set 0 for sticky. */
  duration?: number;
}

interface ToastState extends Required<ToastConfig> {
  id: number;
}

interface ToastContextValue {
  showToast: (config: ToastConfig) => void;
  dismissToast: () => void;
}

const ToastCtx = createContext<ToastContextValue>({
  showToast: () => {},
  dismissToast: () => {},
});

// --------------- Style config ---------------

const TYPE_ICONS: Record<
  ToastType,
  { icon: keyof typeof Ionicons.glyphMap; iconColor: string }
> = {
  success: { icon: 'checkmark-circle', iconColor: '#A5D6A7' },
  error: { icon: 'alert-circle', iconColor: '#EF9A9A' },
  warning: { icon: 'warning', iconColor: '#FFE082' },
  info: { icon: 'information-circle', iconColor: '#90CAF9' },
};

const TOAST_BG_KEY: Record<ToastType, 'toastSuccess' | 'toastError' | 'toastWarning' | 'toastInfo'> = {
  success: 'toastSuccess',
  error: 'toastError',
  warning: 'toastWarning',
  info: 'toastInfo',
};

const HAPTIC_MAP: Record<ToastType, HapticIntent> = {
  success: HapticIntent.JUDGMENT_LOCKED,
  error: HapticIntent.ALERT_TRIGGERED,
  warning: HapticIntent.ALERT_TRIGGERED,
  info: HapticIntent.CONFIRMATION_LIGHT,
};

// --------------- Provider ---------------

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const [toast, setToast] = useState<ToastState | null>(null);
  const translateY = useRef(new Animated.Value(-120)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    Animated.parallel([
      Animated.timing(translateY, {
        toValue: -120,
        duration: DURATION.normal,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 0,
        duration: DURATION.normal,
        useNativeDriver: true,
      }),
    ]).start(() => setToast(null));
  }, [translateY, opacity]);

  const showToast = useCallback(
    (config: ToastConfig) => {
      // Clear previous timer
      if (dismissTimer.current) clearTimeout(dismissTimer.current);

      const id = ++nextId;
      const type = config.type ?? 'info';
      const duration = config.duration ?? 3000;

      setToast({ id, message: config.message, type, duration });

      // Reset + animate in
      translateY.setValue(-120);
      opacity.setValue(0);

      Animated.parallel([
        Animated.spring(translateY, {
          toValue: 0,
          useNativeDriver: true,
          damping: 18,
          stiffness: 200,
        }),
        Animated.timing(opacity, {
          toValue: 1,
          duration: DURATION.fast,
          useNativeDriver: true,
        }),
      ]).start();

      // Haptic feedback
      fireHaptic(HAPTIC_MAP[type], { enabled: settings.hapticsEnabled });

      // Auto-dismiss
      if (duration > 0) {
        dismissTimer.current = setTimeout(dismiss, duration);
      }
    },
    [translateY, opacity, dismiss, settings.hapticsEnabled],
  );

  useEffect(() => {
    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current);
    };
  }, []);

  const value = useMemo(
    () => ({ showToast, dismissToast: dismiss }),
    [showToast, dismiss],
  );

  const cfg = toast ? TYPE_ICONS[toast.type] : null;
  const toastBg = toast ? colors[TOAST_BG_KEY[toast.type]] : undefined;

  return (
    <ToastCtx.Provider value={value}>
      {children}
      {toast && cfg && (
        <Animated.View
          pointerEvents="box-none"
          style={[
            styles.container,
            {
              top: insets.top + (Platform.OS === 'android' ? 8 : 4),
              transform: [{ translateY }],
              opacity,
            },
          ]}
        >
          <Pressable
            onPress={dismiss}
            style={[styles.toast, { backgroundColor: toastBg }]}
            accessibilityRole="alert"
            accessibilityLabel={toast.message}
          >
            <Ionicons name={cfg.icon} size={20} color={cfg.iconColor} />
            <Text style={styles.message} numberOfLines={2}>
              {toast.message}
            </Text>
            <View style={styles.closeArea}>
              <Ionicons name="close" size={16} color="rgba(255,255,255,0.6)" />
            </View>
          </Pressable>
        </Animated.View>
      )}
    </ToastCtx.Provider>
  );
}

export function useToast(): ToastContextValue {
  return useContext(ToastCtx);
}

// --------------- Styles ---------------

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 16,
    right: 16,
    zIndex: 9999,
    alignItems: 'center',
  },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    minHeight: 48,
    maxWidth: 420,
    width: '100%',
    // Shadow
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.25,
        shadowRadius: 8,
      },
      android: { elevation: 8 },
    }),
  },
  message: {
    flex: 1,
    color: '#fff', // Button text on brand background (dark toast)
    fontSize: 14,
    fontWeight: '500',
    marginLeft: 10,
    lineHeight: 20,
  },
  closeArea: {
    padding: 4,
    marginLeft: 8,
  },
});
