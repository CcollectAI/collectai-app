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

/**
 * Icons only. The COLOURS come from the theme at render time.
 *
 * They used to live here as literals — `#34D399`, `#F87171`, `#FBBF24`,
 * `#60A5FA` — straight off the Tailwind palette, on a hardcoded `#1E293B`
 * slate surface. Two consequences:
 *
 *  1. The toast belonged to no theme. `colors.toastSuccess/Error/Warning/Info`
 *     have existed in the light palette, the dark palette AND
 *     `src/theme/highContrast.ts` the whole time with **no reader**, so a user
 *     on high contrast got the same low-contrast toast as everyone else —
 *     an accessibility mode that silently did nothing here.
 *  2. The most common toast in the app ("Watching — we'll alert you…") was a
 *     blue banner with a blue glyph, which is not this app's colour.
 */
const TYPE_ICONS: Record<ToastType, keyof typeof Ionicons.glyphMap> = {
  success: 'checkmark-circle',
  error: 'alert-circle',
  warning: 'warning',
  info: 'information-circle',
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
  // Safe here: ToastProvider is mounted INSIDE SettingsProvider
  // (app/_layout.tsx), and useAppTheme reads nothing else.
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

  // The toast is an INVERSE surface: `colors.toastSuccess/Error/Warning/Info`
  // are dark in the light palette, the dark palette and both high-contrast
  // palettes. So the surface is themed, but the glyph is not — and that is
  // deliberate, not an oversight of the "never hardcode a colour on a themed
  // background" rule.
  //
  // Sourcing the glyph from the palette is actively WRONG here, because those
  // tokens are built for a LIGHT background and go dark-on-dark on this one:
  // `success` is #059669 in the light palette and #006600 in high-contrast
  // light, against a #1B5E20 / #003300 surface. `brand.light` is worse — it
  // INVERTS to #003D99 in high-contrast dark. Both are unreadable.
  //
  // These four are the on-dark set. Any new one must be light enough to sit on
  // the darkest toast surface in `highContrast.ts`.
  const cfg = toast
    ? {
        icon: TYPE_ICONS[toast.type],
        surface: {
          success: colors.toastSuccess,
          error: colors.toastError,
          warning: colors.toastWarning,
          info: colors.toastInfo,
        }[toast.type],
        iconColor: {
          success: '#34D399',
          error: '#F87171',
          warning: '#FBBF24',
          // Tiffany light, replacing a Tailwind blue. Info is the most common
          // toast in the app ("Watching — we'll alert you…"), so it is the one
          // that most needs to look like Sparrow.
          info: '#AEE6E1',
        }[toast.type],
      }
    : null;

  return (
    <ToastCtx.Provider value={value}>
      {children}
      {toast && cfg && (
        <Animated.View
          style={[
            styles.container,
            {
              top: insets.top + (Platform.OS === 'android' ? 8 : 4),
              transform: [{ translateY }],
              opacity,
              // pointerEvents in style (RN 0.81+) — legacy prop on
              // Animated.View can be silently ignored, swallowing taps
              // to whatever sits behind the toast strip.
              pointerEvents: 'box-none',
            },
          ]}
        >
          <Pressable
            onPress={dismiss}
            style={[styles.toast, { backgroundColor: cfg.surface, borderLeftColor: cfg.iconColor }]}
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
    borderRadius: 14,
    borderLeftWidth: 4,
    // backgroundColor comes from the theme per type — see TYPE_ICONS above.
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
