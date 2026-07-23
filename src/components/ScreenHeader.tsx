/**
 * ScreenHeader — the one flat top bar used across non-tab screens.
 *
 * Why this exists: the native stack header on iOS 26 wraps every bar-button
 * item (back chevron, right-side icons) in a translucent "liquid glass" pill
 * with a shadow, which reads as too prominent. react-native-screens 4.16 has
 * no prop to opt out. The repo's escape hatch (see app/inbox.tsx and the tab
 * screens) is `headerShown: false` + an in-body header of bare pressables —
 * plain icons, no capsule. This centralises that pattern so every screen shows
 * the SAME flat top-right icons (chat + settings) instead of each screen
 * hand-rolling its own.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';

type Props = {
  /** Centre/left title. Omit for an icon-only bar. */
  title?: string;
  /** Show the back chevron (defaults to true). */
  showBack?: boolean;
  /** Show the chat + settings cluster on the right (defaults to true). */
  showActions?: boolean;
};

export default function ScreenHeader({ title, showBack = true, showActions = true }: Props) {
  const router = useRouter();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  return (
    <View
      style={[
        styles.row,
        styles.elevated,
        {
          paddingTop: insets.top + 6,
          backgroundColor: colors.background,
          // Hairline + shadow so the header reads as a distinct floating bar and
          // the (white) body content sits clearly BELOW it instead of bleeding
          // up into it — a hairline alone is too subtle on white-on-white.
          borderBottomWidth: StyleSheet.hairlineWidth,
          borderBottomColor: colors.border,
        },
      ]}
    >
      <View style={styles.side}>
        {showBack && (
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              router.back();
            }}
            style={styles.iconBtn}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={26} color={colors.text} />
          </AnimatedPressable>
        )}
      </View>

      {title ? (
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {title}
        </Text>
      ) : (
        <View style={styles.flex} />
      )}

      <View style={styles.side}>
        {showActions && (
          <>
            <InboxHeaderButton color={colors.text} size={22} />
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                router.push('/settings');
              }}
              style={styles.iconBtn}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel="Open settings"
            >
              <Ionicons name="settings-outline" size={22} color={colors.text} />
            </AnimatedPressable>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  // Distinct floating bar: a soft shadow + a high zIndex so scrolling body
  // content passes UNDER the header rather than appearing to merge into it.
  elevated: {
    zIndex: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 4,
  },
  // Fixed-width sides keep the title centred and both icon clusters aligned
  // across every screen regardless of how many icons each side has.
  side: { flexDirection: 'row', alignItems: 'center', minWidth: 76 },
  flex: { flex: 1 },
  title: { flex: 1, fontSize: 18, fontWeight: '800', textAlign: 'center' },
  iconBtn: { padding: 4 },
});
