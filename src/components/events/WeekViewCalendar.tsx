/**
 * WeekViewCalendar — 7-day column view with time slots for events.
 */
import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Dimensions,
  GestureResponderEvent,
} from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { CollectorsEvent } from '@/data/events';
import { parseEventDate } from '@/lib/calendar';

const SCREEN_WIDTH = Dimensions.get('window').width;
const HOUR_HEIGHT = 60;
const START_HOUR = 8;
const END_HOUR = 22;
const TOTAL_HOURS = END_HOUR - START_HOUR;
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const COL_WIDTH = (SCREEN_WIDTH - 48) / 7; // 48 = time label width

interface WeekViewCalendarProps {
  events: CollectorsEvent[];
  onEventPress?: (event: CollectorsEvent) => void;
  onWeekChange?: (weekStart: Date) => void;
}

function getMonday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function formatWeekRange(monday: Date): string {
  const sunday = addDays(monday, 6);
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  return `${monday.toLocaleDateString('en-US', opts)} – ${sunday.toLocaleDateString('en-US', opts)}`;
}

export const WeekViewCalendar = React.memo(function WeekViewCalendar({
  events,
  onEventPress,
  onWeekChange,
}: WeekViewCalendarProps) {
  const { colors } = useAppTheme();
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));

  const navigateWeek = useCallback(
    (direction: -1 | 1) => {
      setWeekStart((prev) => {
        const next = addDays(prev, direction * 7);
        onWeekChange?.(next);
        return next;
      });
    },
    [onWeekChange],
  );

  // Map events to their day column and time position
  const eventBlocks = useMemo(() => {
    const blocks: Array<{
      event: CollectorsEvent;
      dayIndex: number;
      topOffset: number;
      height: number;
    }> = [];

    for (const evt of events) {
      if (!evt.date) continue;
      const start = parseEventDate(evt.date, evt.time);
      const dayDiff = Math.floor(
        (start.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24),
      );
      if (dayDiff < 0 || dayDiff > 6) continue;

      const startHour = start.getHours() + start.getMinutes() / 60;
      if (startHour < START_HOUR || startHour >= END_HOUR) continue;

      const topOffset = (startHour - START_HOUR) * HOUR_HEIGHT;
      const durationHrs = evt.endDate
        ? (new Date(evt.endDate).getTime() - start.getTime()) / (1000 * 60 * 60)
        : 1;
      const height = Math.max(Math.min(durationHrs, TOTAL_HOURS) * HOUR_HEIGHT, 30);

      blocks.push({ event: evt, dayIndex: dayDiff, topOffset, height });
    }
    return blocks;
  }, [events, weekStart]);

  // Current time indicator
  const now = new Date();
  const nowMonday = getMonday(now);
  const isThisWeek = weekStart.getTime() === nowMonday.getTime();
  const nowDayIndex = isThisWeek ? (now.getDay() === 0 ? 6 : now.getDay() - 1) : -1;
  const nowHour = now.getHours() + now.getMinutes() / 60;
  const nowTop = isThisWeek && nowHour >= START_HOUR && nowHour < END_HOUR
    ? (nowHour - START_HOUR) * HOUR_HEIGHT
    : -1;

  return (
    <View style={styles.container}>
      {/* Week navigation */}
      <View style={[styles.navRow, { borderBottomColor: colors.border }]}>
        <AnimatedPressable onPress={() => navigateWeek(-1)} accessibilityLabel="Previous week">
          <Text style={[styles.navArrow, { color: colors.accent }]}>‹</Text>
        </AnimatedPressable>
        <Text style={[styles.weekLabel, { color: colors.text }]}>
          {formatWeekRange(weekStart)}
        </Text>
        <AnimatedPressable onPress={() => navigateWeek(1)} accessibilityLabel="Next week">
          <Text style={[styles.navArrow, { color: colors.accent }]}>›</Text>
        </AnimatedPressable>
      </View>

      {/* Day headers */}
      <View style={[styles.dayHeaderRow, { borderBottomColor: colors.border }]}>
        <View style={styles.timeGutter} />
        {DAY_LABELS.map((label, i) => {
          const date = addDays(weekStart, i);
          const isToday =
            date.toDateString() === now.toDateString();
          return (
            <View key={label} style={[styles.dayHeaderCell, { width: COL_WIDTH }]}>
              <Text style={[styles.dayLabel, { color: colors.muted }]}>{label}</Text>
              <Text
                style={[
                  styles.dayNumber,
                  { color: isToday ? colors.accent : colors.text },
                  isToday && { fontWeight: '700' },
                ]}
              >
                {date.getDate()}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Time grid */}
      <ScrollView style={styles.gridScroll} showsVerticalScrollIndicator={false}>
        <View style={styles.gridContainer}>
          {/* Time labels */}
          <View style={styles.timeGutter}>
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <View key={i} style={[styles.hourRow, { height: HOUR_HEIGHT }]}>
                <Text style={[styles.timeLabel, { color: colors.muted }]}>
                  {START_HOUR + i}:00
                </Text>
              </View>
            ))}
          </View>

          {/* Day columns */}
          <View style={styles.columnsContainer}>
            {DAY_LABELS.map((_, dayIdx) => (
              <View key={dayIdx} style={[styles.dayColumn, { width: COL_WIDTH, borderLeftColor: colors.border }]}>
                {/* Hour grid lines */}
                {Array.from({ length: TOTAL_HOURS }, (__, hr) => (
                  <View
                    key={hr}
                    style={[
                      styles.hourGridLine,
                      { height: HOUR_HEIGHT, borderBottomColor: colors.border },
                    ]}
                  />
                ))}
              </View>
            ))}

            {/* Event blocks */}
            {eventBlocks.map(({ event, dayIndex, topOffset, height }) => (
              <AnimatedPressable
                key={event.id}
                style={[
                  styles.eventBlock,
                  {
                    left: dayIndex * COL_WIDTH,
                    top: topOffset,
                    height,
                    width: COL_WIDTH - 4,
                    backgroundColor: colors.accent + '30',
                    borderLeftColor: colors.accent,
                  },
                ]}
                onPress={() => onEventPress?.(event)}
                accessibilityLabel={`${event.title}, ${parseEventDate(event.date, event.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                accessibilityRole="button"
              >
                <Text
                  style={[styles.eventBlockTitle, { color: colors.text }]}
                  numberOfLines={2}
                >
                  {event.title}
                </Text>
              </AnimatedPressable>
            ))}

            {/* Current time indicator */}
            {nowTop >= 0 && (
              <View
                style={[
                  styles.nowLine,
                  {
                    top: nowTop,
                    left: nowDayIndex * COL_WIDTH,
                    width: COL_WIDTH,
                  },
                ]}
              >
                <View style={[styles.nowDot, { backgroundColor: colors.error }]} />
                <View style={[styles.nowLineBar, { backgroundColor: colors.error }]} />
              </View>
            )}
          </View>
        </View>
      </ScrollView>
    </View>
  );
});

const styles = StyleSheet.create({
  container: { flex: 1 },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  navArrow: { fontSize: 28, fontWeight: '300', paddingHorizontal: 12 },
  weekLabel: { fontSize: 15, fontWeight: '600' },
  dayHeaderRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    paddingVertical: 8,
  },
  dayHeaderCell: { alignItems: 'center' },
  dayLabel: { fontSize: 11, fontWeight: '500', textTransform: 'uppercase' },
  dayNumber: { fontSize: 16, fontWeight: '500', marginTop: 2 },
  gridScroll: { flex: 1 },
  gridContainer: { flexDirection: 'row' },
  timeGutter: { width: 48 },
  hourRow: { justifyContent: 'flex-start', paddingTop: 2, paddingLeft: 6 },
  timeLabel: { fontSize: 10, fontWeight: '500' },
  columnsContainer: { flex: 1, position: 'relative' },
  dayColumn: { position: 'absolute', top: 0, borderLeftWidth: StyleSheet.hairlineWidth },
  hourGridLine: { borderBottomWidth: StyleSheet.hairlineWidth },
  eventBlock: {
    position: 'absolute',
    borderLeftWidth: 3,
    borderRadius: 4,
    paddingHorizontal: 4,
    paddingVertical: 2,
    overflow: 'hidden',
    marginLeft: 2,
  },
  eventBlockTitle: { fontSize: 10, fontWeight: '600', lineHeight: 13 },
  nowLine: { position: 'absolute', flexDirection: 'row', alignItems: 'center', zIndex: 10 },
  nowDot: { width: 8, height: 8, borderRadius: 4, marginLeft: -4 },
  nowLineBar: { flex: 1, height: 2 },
});
