/**
 * SlowLoadNotice — the words that go with a wait.
 *
 * Renders nothing until `useSlowLoad` says the wait has passed 3s, so a fast
 * load is silent and only a genuinely slow one speaks. Sits under a skeleton or
 * spinner; it replaces nothing and hides nothing.
 *
 * It is reassurance, NOT an error. Muted colour, no icon-of-alarm, no retry
 * button — the request is still in flight and offering a retry here would
 * invite a second identical query while the first is still running. If the wait
 * ends in failure, the screen's existing error branch owns that.
 *
 * `accessibilityLiveRegion="polite"` + `accessibilityRole="alert"` so VoiceOver
 * and TalkBack announce it when it appears — a message a blind user never hears
 * is the same silence we are fixing.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { text as textToken } from '@/theme/tokens';

type SlowLoadNoticeProps = {
  /** From useSlowLoad(isLoading). */
  isSlow: boolean;
  /** From useSlowLoad(isLoading). Escalates the wording after ~10s. */
  isVerySlow?: boolean;
  /** Optional override, e.g. "Searching is taking longer than usual". */
  message?: string;
};

export const SlowLoadNotice = React.memo(function SlowLoadNotice({
  isSlow,
  isVerySlow = false,
  message,
}: SlowLoadNoticeProps) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  if (!isSlow) return null;

  const body =
    message ??
    (isVerySlow
      ? t('common.slow_load_still_working')
      : t('common.slow_load_working'));

  return (
    <View
      style={styles.container}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <Text style={[styles.text, { color: colors.muted }]}>{body}</Text>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 32,
    paddingTop: 12,
    alignItems: 'center',
  },
  text: {
    fontSize: textToken.sm,
    textAlign: 'center',
    lineHeight: 20,
  },
});
