/**
 * EventCountdown - Displays a countdown timer to an event.
 * Automatically updates and shows appropriate labels.
 */

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { getCountdown, parseEventDate } from '@/lib/calendar';

interface Props {
  date: string;
  time?: string;
  size?: 'small' | 'medium' | 'large';
  colors: {
    text: string;
    muted: string;
    accent: string;
    background: string;
  };
  showSeconds?: boolean;
}

export function EventCountdown({
  date,
  time,
  size = 'medium',
  colors,
  showSeconds = false,
}: Props) {
  const [countdown, setCountdown] = useState(() =>
    getCountdown(parseEventDate(date, time))
  );

  useEffect(() => {
    const targetDate = parseEventDate(date, time);

    // Update immediately
    setCountdown(getCountdown(targetDate));

    // Update every second if showing seconds, otherwise every minute
    const interval = setInterval(
      () => setCountdown(getCountdown(targetDate)),
      showSeconds ? 1000 : 60000
    );

    return () => clearInterval(interval);
  }, [date, time, showSeconds]);

  if (countdown.isPast) {
    return (
      <View style={[styles.container, styles[`container_${size}`]]}>
        <Text style={[styles.pastText, styles[`text_${size}`], { color: colors.muted }]}>
          Event ended
        </Text>
      </View>
    );
  }

  // For "Today" or "Tomorrow", show simple label
  if (countdown.isToday || countdown.isTomorrow) {
    return (
      <View
        style={[
          styles.container,
          styles[`container_${size}`],
          { backgroundColor: colors.accent + '15' },
        ]}
      >
        <Text
          style={[
            styles.label,
            styles[`text_${size}`],
            { color: colors.accent, fontWeight: '600' },
          ]}
        >
          {countdown.formatted}
        </Text>
      </View>
    );
  }

  // Show detailed countdown for upcoming events
  return (
    <View
      style={[
        styles.container,
        styles[`container_${size}`],
        { backgroundColor: colors.background },
      ]}
    >
      <CountdownSegment
        value={countdown.days}
        label="days"
        size={size}
        colors={colors}
      />
      <Text style={[styles.separator, { color: colors.muted }]}>:</Text>
      <CountdownSegment
        value={countdown.hours}
        label="hrs"
        size={size}
        colors={colors}
      />
      <Text style={[styles.separator, { color: colors.muted }]}>:</Text>
      <CountdownSegment
        value={countdown.minutes}
        label="min"
        size={size}
        colors={colors}
      />
      {showSeconds && (
        <>
          <Text style={[styles.separator, { color: colors.muted }]}>:</Text>
          <CountdownSegment
            value={countdown.seconds}
            label="sec"
            size={size}
            colors={colors}
          />
        </>
      )}
    </View>
  );
}

function CountdownSegment({
  value,
  label,
  size,
  colors,
}: {
  value: number;
  label: string;
  size: 'small' | 'medium' | 'large';
  colors: { text: string; muted: string };
}) {
  const fontSize = size === 'small' ? 16 : size === 'large' ? 28 : 22;
  const labelSize = size === 'small' ? 8 : size === 'large' ? 11 : 9;

  return (
    <View style={styles.segment}>
      <Text style={[styles.value, { fontSize, color: colors.text }]}>
        {String(value).padStart(2, '0')}
      </Text>
      <Text style={[styles.segmentLabel, { fontSize: labelSize, color: colors.muted }]}>
        {label}
      </Text>
    </View>
  );
}

// Compact badge version for list items
export function CountdownBadge({
  date,
  time,
  colors,
}: {
  date: string;
  time?: string;
  colors: { text: string; muted: string; accent: string };
}) {
  const [countdown, setCountdown] = useState(() =>
    getCountdown(parseEventDate(date, time))
  );

  useEffect(() => {
    const targetDate = parseEventDate(date, time);
    setCountdown(getCountdown(targetDate));

    const interval = setInterval(
      () => setCountdown(getCountdown(targetDate)),
      60000
    );

    return () => clearInterval(interval);
  }, [date, time]);

  if (countdown.isPast) {
    return (
      <View style={[styles.badge, { backgroundColor: colors.muted + '20' }]}>
        <Text style={[styles.badgeText, { color: colors.muted }]}>Ended</Text>
      </View>
    );
  }

  const isUrgent = countdown.days === 0 || countdown.isToday;
  const bgColor = isUrgent ? colors.accent + '20' : colors.muted + '15';
  const textColor = isUrgent ? colors.accent : colors.text;

  return (
    <View style={[styles.badge, { backgroundColor: bgColor }]}>
      <Text style={[styles.badgeText, { color: textColor }]}>
        {countdown.formatted}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    padding: 8,
  },
  container_small: {
    padding: 6,
  },
  container_medium: {
    padding: 10,
  },
  container_large: {
    padding: 14,
  },
  segment: {
    alignItems: 'center',
    minWidth: 36,
  },
  value: {
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  segmentLabel: {
    fontWeight: '500',
    marginTop: 2,
  },
  separator: {
    fontSize: 18,
    fontWeight: '300',
    marginHorizontal: 4,
  },
  label: {
    fontSize: 14,
  },
  text_small: {
    fontSize: 12,
  },
  text_medium: {
    fontSize: 14,
  },
  text_large: {
    fontSize: 16,
  },
  pastText: {
    fontStyle: 'italic',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
});

export default EventCountdown;
