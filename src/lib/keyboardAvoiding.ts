/**
 * The ONE `behavior` every KeyboardAvoidingView in the app uses, on both
 * platforms.
 *
 * WHY 'padding' on Android too: the app draws edge-to-edge (Expo SDK 54,
 * targetSdk 36), and an edge-to-edge window is NOT resized when the soft
 * keyboard opens — `windowSoftInputMode=adjustResize` no longer moves anything.
 * So the old `Platform.OS === 'ios' ? 'padding' : undefined` left Android with
 * no keyboard handling at all. Walked on Android 2026-09-22: in a DM the
 * message box sat at y=2002-2101 under a keyboard that started at y≈1520 —
 * a member could not see what they were typing, and Send was unreachable.
 *
 * `npm run check:keyboard-avoiding` fails on any KeyboardAvoidingView that
 * does not take its behavior from here.
 */
export const KEYBOARD_AVOIDING_BEHAVIOR = 'padding' as const;
