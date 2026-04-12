/**
 * WeekViewCalendar — Professional 7-day column view with time slots.
 * Features: week navigation, today indicator, event blocks with time + title,
 * current time red line, proper day headers with today highlight.
 */
import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { CollectorsEvent } from '@/data/events';
import { parseEventDate } from '@/lib/calendar';

const SCREEN_WIDTH = Dimensions.get('window').width;
const HOUR_HEIGHT = 56;
const START_HOUR = 7;
const END_HOUR = 23;
const TOTAL_HOURS = END_HOUR - START_HOUR;
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TIME_GUTTER_WIDTH = 46;
const COL_WIDTH = (SCREEN_WIDTH - TIME_GUTTER_WIDTH - 16) / 7;

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
  const scrollRef = useRef<ScrollView>(null);
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

  const goToThisWeek = useCallback(() => {
    setWeekStart(getMonday(new Date()));
  }, []);

  // Auto-scroll to current hour on mount
  useEffect(() => {
    const h = new Date().getHours();
    if (h >= START_HOUR && h < END_HOUR) {
      const offset = Math.max(0, (h - START_HOUR - 1) * HOUR_HEIGHT);
      setTimeout(() => scrollRef.current?.scrollTo({ y: offset, animated: false }), 100);
    }
  }, []);

  const eventBlocks = useMemo(() => {
    const blocks: {
      event: CollectorsEvent;
      dayIndex: number;
      topOffset: number;
      height: number;
      startTime: string;
    }[] = [];

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
      const height = Math.max(Math.min(durationHrs, TOTAL_HOURS) * HOUR_HEIGHT, 28);
      const startTime = start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      blocks.push({ event: evt, dayIndex: dayDiff, topOffset, height, startTime });
    }
    return blocks;
  }, [events, weekStart]);

  const now = new Date();
  const nowMonday = getMonday(now);
  const isThisWeek = weekStart.getTime() === nowMonday.getTime();
  const nowDayIndex = isThisWeek ? (now.getDay() === 0 ? 6 : now.getDay() - 1) : -1;
  const nowHour = now.getHours() + now.getMinutes() / 60;
  const nowTop = isThisWeek && nowHour >= START_HOUR && nowHour < END_HOUR
    ? (nowHour - START_HOUR) * HOUR_HEIGHT
    : -1;

  // Count events this week
  const weekEventCount = eventBlocks.length;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Week navigation */}
      <View style={[styles.navRow, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => navigateWeek(-1)}
          style={[styles.navBtn, { backgroundColor: colors.border + '40' }]}
          accessibilityLabel="Previous week"
          accessibilityRole="button"
        >
          <Ionicons name="chevron-back" size={16} color={colors.text} />
        </AnimatedPressable>

        <AnimatedPressable onPress={goToThisWeek} accessibilityLabel="Go to current week" accessibilityRole="button">
          <Text style={[styles.weekLabel, { color: colors.text }]}>
            {formatWeekRange(weekStart)}
          </Text>
          <Text style={[styles.weekMeta, { color: colors.muted }]}>
            {isThisWeek ? 'This week' : `${weekEventCount} event${weekEventCount !== 1 ? 's' : ''}`}
          </Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => navigateWeek(1)}
          style={[styles.navBtn, { backgroundColor: colors.border + '40' }]}
          accessibilityLabel="Next week"
          accessibilityRole="button"
        >
          <Ionicons name="chevron-forward" size={16} color={colors.text} />
        </AnimatedPressable>
      </View>

      {/* Day headers */}
      <View style={[styles.dayHeaderRow, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <View style={styles.timeGutter} />
        {DAY_LABELS.map((label, i) => {
          const date = addDays(weekStart, i);
          const isToday = date.toDateString() === now.toDateString();
          return (
            <View key={label} style={[styles.dayHeaderCell, { width: COL_WIDTH }]}>
              <Text style={[
                styles.dayLabel,
                { color: isToday ? colors.accent : colors.muted },
                isToday && { fontWeight: '700' },
              ]}>
                {label}
              </Text>
              <View style={[
                styles.dayNumberCircle,
                isToday && { backgroundColor: colors.accent },
              ]}>
                <Text style={[
                  styles.dayNumber,
                  { color: isToday ? '#FFFFFF' : colors.text },
                  isToday && { fontWeight: '700' },
                ]}>
                  {date.getDate()}
                </Text>
              </View>
            </View>
          );
        })}
      </View>

      {/* Time grid */}
      <ScrollView ref={scrollRef} style={styles.gridScroll} showsVerticalScrollIndicator={false}>
        <View style={styles.gridContainer}>
          {/* Time labels */}
          <View style={styles.timeGutter}>
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <View key={i} style={[styles.hourRow, { height: HOUR_HEIGHT }]}>
                <Text style={[styles.timeLabel, { color: colors.muted }]}>
                  {String(START_HOUR + i).padStart(2, '0')}:00
                </Text>
              </View>
            ))}
          </View>

          {/* Day columns with grid lines */}
          <View style={styles.columnsContainer}>
            {DAY_LABELS.map((_, dayIdx) => (
              <View
                key={dayIdx}
                style={[
                  styles.dayColumn,
                  {
                    width: COL_WIDTH,
                    left: dayIdx * COL_WIDTH,
                    borderLeftColor: colors.border + '60',
                  },
                ]}
              >
                {Array.from({ length: TOTAL_HOURS }, (__, hr) => (
                  <View
                    key={hr}
                    style={[
                      styles.hourGridLine,
                      { height: HOUR_HEIGHT, borderBottomColor: colors.border + '40' },
                    ]}
                  />
                ))}
              </View>
            ))}

            {/* Event blocks */}
            {eventBlocks.map(({ event, dayIndex, topOffset, height, startTime }) => (
              <AnimatedPressable
                key={event.id}
                style={[
                  styles.eventBlock,
                  {
                    left: dayIndex * COL_WIDTH + 1,
                    top: topOffset,
                    height,
                    width: COL_WIDTH - 3,
                    backgroundColor: colors.accent + '20',
                    borderLeftColor: colors.accent,
                  },
                ]}
                onPress={() => onEventPress?.(event)}
                accessibilityLabel={`${event.title}, ${startTime}`}
                accessibilityRole="button"
              >
                <Text style={[styles.eventBlockTime, { color: colors.accent }]} numberOfLines={1}>
                  {startTime}
                </Text>
                <Text style={[styles.eventBlockTitle, { color: colors.text }]} numberOfLines={2}>
                  {event.title}
                </Text>
              </AnimatedPressable>
            ))}

            {/* Current time indicator */}
            {nowTop >= 0 && (
              <View
                style={[
                  styles.nowLine,
                  { top: nowTop, width: 7 * COL_WIDTH },
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
  container: {
    flex: 1,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  navBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekLabel: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },
  weekMeta: {
    fontSize: 11,
    fontWeight: '500',
    textAlign: 'center',
    marginTop: 2,
  },
  dayHeaderRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    paddingVertical: 8,
    paddingBottom: 10,
  },
  dayHeaderCell: {
    alignItems: 'center',
    gap: 4,
  },
  dayLabel: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  dayNumberCircle: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayNumber: {
    fontSize: 13,
    fontWeight: '500',
  },
  gridScroll: {
    flex: 1,
  },
  gridContainer: {
    flexDirection: 'row',
  },
  timeGutter: {
    width: TIME_GUTTER_WIDTH,
  },
  hourRow: {
    justifyContent: 'flex-start',
    paddingTop: 0,
    paddingLeft: 8,
  },
  timeLabel: {
    fontSize: 10,
    fontWeight: '500',
    marginTop: -6,
  },
  columnsContainer: {
    flex: 1,
    position: 'relative',
  },
  dayColumn: {
    position: 'absolute',
    top: 0,
    borderLeftWidth: StyleSheet.hairlineWidth,
  },
  hourGridLine: {
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  eventBlock: {
    position: 'absolute',
    borderLeftWidth: 3,
    borderRadius: 6,
    paddingHorizontal: 3,
    paddingVertical: 2,
    overflow: 'hidden',
  },
  eventBlockTime: {
    fontSize: 8,
    fontWeight: '700',
    lineHeight: 11,
  },
  eventBlockTitle: {
    fontSize: 9,
    fontWeight: '600',
    lineHeight: 12,
  },
  nowLine: {
    position: 'absolute',
    left: 0,
    flexDirection: 'row',
    alignItems: 'center',
    zIndex: 10,
  },
  nowDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginLeft: -4,
  },
  nowLineBar: {
    flex: 1,
    height: 1.5,
  },
});
