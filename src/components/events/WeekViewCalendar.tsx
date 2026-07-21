/**
 * WeekViewCalendar — a full-week overview time-grid for phones.
 *
 * All 7 days are visible at once (fit to screen width) so you get an actual
 * week overview at a glance, and the hour rows are short enough that most of
 * the day is on screen. Events render as compact blocks — tap one for details.
 * Overlapping events split into side-by-side lanes; the current time shows as a
 * red line; today and the weekend get a subtle tint for orientation.
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
import { useSettings } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { CollectorsEvent } from '@/data/events';
import { parseEventDate } from '@/lib/calendar';

const SCREEN_WIDTH = Dimensions.get('window').width;
// Short hour rows so most of the day fits without scrolling — this is the
// "overview" the tall 64px rows were killing.
const HOUR_HEIGHT = 48;
const START_HOUR = 7;
const END_HOUR = 23;
const TOTAL_HOURS = END_HOUR - START_HOUR;
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TIME_GUTTER_WIDTH = 44;
// All 7 days share the width — no horizontal scroll, so the whole week is
// visible at once.
const COL_WIDTH = (SCREEN_WIDTH - TIME_GUTTER_WIDTH) / 7;
const GRID_WIDTH = COL_WIDTH * 7;
const GRID_HEIGHT = TOTAL_HOURS * HOUR_HEIGHT;

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
  const { settings } = useSettings();
  const scrollRef = useRef<ScrollView>(null);
  const lastScrolledWeek = useRef<number>(0);
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));

  const tick = useCallback(
    (intent: HapticIntent = HapticIntent.CONFIRMATION_LIGHT) =>
      fireHaptic(intent, { enabled: settings.hapticsEnabled }),
    [settings.hapticsEnabled],
  );

  const navigateWeek = useCallback(
    (direction: -1 | 1) => {
      tick();
      setWeekStart((prev) => {
        const next = addDays(prev, direction * 7);
        onWeekChange?.(next);
        return next;
      });
    },
    [onWeekChange, tick],
  );

  const goToThisWeek = useCallback(() => {
    tick();
    setWeekStart(getMonday(new Date()));
  }, [tick]);

  const { blocks, hiddenCount } = useMemo(() => {
    type Block = {
      event: CollectorsEvent;
      dayIndex: number;
      topOffset: number;
      height: number;
      startTime: string;
      lane: number;
      laneCount: number;
    };

    let hidden = 0;
    const perDay: Record<number, Omit<Block, "lane" | "laneCount">[]> = {};
    for (const evt of events) {
      if (!evt.date) continue;
      const start = parseEventDate(evt.date, evt.time);
      const dayDiff = Math.floor(
        (start.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24),
      );
      if (dayDiff < 0 || dayDiff > 6) continue;

      const startHour = start.getHours() + start.getMinutes() / 60;
      // In this week but outside the visible hours — count it so the header can
      // tell the user rather than making the event silently disappear.
      if (startHour < START_HOUR || startHour >= END_HOUR) {
        hidden++;
        continue;
      }

      const topOffset = (startHour - START_HOUR) * HOUR_HEIGHT;
      const durationHrs = evt.endDate
        ? (new Date(evt.endDate).getTime() - start.getTime()) / (1000 * 60 * 60)
        : 1;
      const height = Math.max(Math.min(durationHrs, TOTAL_HOURS) * HOUR_HEIGHT, 26);
      const startTime = start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      (perDay[dayDiff] ??= []).push({
        event: evt,
        dayIndex: dayDiff,
        topOffset,
        height,
        startTime,
      });
    }

    // Per day, assign each event to a horizontal lane so overlapping events
    // sit side-by-side instead of stacking on top of each other.
    const out: Block[] = [];
    for (const dayKey of Object.keys(perDay)) {
      const dayEvents = perDay[Number(dayKey)]!.sort((a, b) => a.topOffset - b.topOffset);
      const laneEnds: number[] = [];
      const assigned: Block[] = [];
      for (const e of dayEvents) {
        let lane = laneEnds.findIndex((end) => end <= e.topOffset);
        if (lane === -1) {
          lane = laneEnds.length;
          laneEnds.push(0);
        }
        laneEnds[lane] = e.topOffset + e.height;
        assigned.push({ ...e, lane, laneCount: 0 });
      }
      for (const e of assigned) {
        let overlapping = 0;
        for (const other of assigned) {
          const aTop = e.topOffset;
          const aBot = e.topOffset + e.height;
          const bTop = other.topOffset;
          const bBot = other.topOffset + other.height;
          if (aTop < bBot && bTop < aBot) overlapping++;
        }
        e.laneCount = Math.max(overlapping, e.lane + 1);
        out.push(e);
      }
    }
    return { blocks: out, hiddenCount: hidden };
  }, [events, weekStart]);

  const now = new Date();
  const nowMonday = getMonday(now);
  const isThisWeek = weekStart.getTime() === nowMonday.getTime();
  const nowDayIndex = isThisWeek ? (now.getDay() === 0 ? 6 : now.getDay() - 1) : -1;
  const nowHour = now.getHours() + now.getMinutes() / 60;
  const nowTop = isThisWeek && nowHour >= START_HOUR && nowHour < END_HOUR
    ? (nowHour - START_HOUR) * HOUR_HEIGHT
    : -1;

  const weekEventCount = blocks.length;

  // On landing on a week, scroll vertically so its events are in view: this
  // week's current hour, else the earliest event. Runs once per distinct week.
  useEffect(() => {
    if (lastScrolledWeek.current === weekStart.getTime()) return;
    lastScrolledWeek.current = weekStart.getTime();

    let targetTop: number | null = null;
    if (isThisWeek && nowHour >= START_HOUR && nowHour < END_HOUR) {
      targetTop = (nowHour - START_HOUR - 1) * HOUR_HEIGHT;
    } else if (blocks.length > 0) {
      targetTop = Math.min(...blocks.map((b) => b.topOffset)) - HOUR_HEIGHT / 2;
    }
    if (targetTop !== null) {
      const y = Math.max(0, targetTop);
      setTimeout(() => scrollRef.current?.scrollTo({ y, animated: false }), 80);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekStart, blocks]);

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
          <Ionicons name="chevron-back" size={18} color={colors.text} />
        </AnimatedPressable>

        <AnimatedPressable onPress={goToThisWeek} accessibilityLabel="Go to current week" accessibilityRole="button">
          <Text style={[styles.weekLabel, { color: colors.text }]}>
            {formatWeekRange(weekStart)}
          </Text>
          <Text style={[styles.weekMeta, { color: colors.muted }]}>
            {isThisWeek ? 'This week' : `${weekEventCount} event${weekEventCount !== 1 ? 's' : ''}`}
            {hiddenCount > 0 ? ` · ${hiddenCount} off-hours` : ''}
          </Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => navigateWeek(1)}
          style={[styles.navBtn, { backgroundColor: colors.border + '40' }]}
          accessibilityLabel="Next week"
          accessibilityRole="button"
        >
          <Ionicons name="chevron-forward" size={18} color={colors.text} />
        </AnimatedPressable>
      </View>

      {/* Day headers — all 7, fixed above the scrolling grid */}
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
                  {String(START_HOUR + i).padStart(2, '0')}
                </Text>
              </View>
            ))}
          </View>

          {/* Day columns + events */}
          <View style={[styles.columnsContainer, { width: GRID_WIDTH, height: GRID_HEIGHT }]}>
            {DAY_LABELS.map((_, dayIdx) => {
              const isTodayCol = dayIdx === nowDayIndex;
              const isWeekend = dayIdx >= 5;
              return (
                <View
                  key={dayIdx}
                  style={[
                    styles.dayColumn,
                    {
                      width: COL_WIDTH,
                      left: dayIdx * COL_WIDTH,
                      borderLeftColor: colors.border + '60',
                    },
                    isWeekend && { backgroundColor: colors.muted + '0A' },
                    isTodayCol && { backgroundColor: colors.accent + '0F' },
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
              );
            })}

            {/* Event blocks — overlapping events split horizontally into lanes */}
            {blocks.map(({ event, dayIndex, topOffset, height, startTime, lane, laneCount }) => {
              const laneWidth = (COL_WIDTH - 2) / laneCount;
              const tiny = laneWidth < 40 || height < 30;
              return (
                <AnimatedPressable
                  key={event.id}
                  style={[
                    styles.eventBlock,
                    {
                      left: dayIndex * COL_WIDTH + 1 + lane * laneWidth,
                      top: topOffset,
                      height,
                      width: laneWidth - 1,
                      backgroundColor: colors.accent + '22',
                      borderLeftColor: colors.accent,
                    },
                  ]}
                  onPress={() => {
                    tick();
                    onEventPress?.(event);
                  }}
                  accessibilityLabel={`${event.title}, ${startTime}`}
                  accessibilityRole="button"
                >
                  {!tiny && (
                    <Text style={[styles.eventBlockTime, { color: colors.accent }]} numberOfLines={1}>
                      {startTime}
                    </Text>
                  )}
                  <Text
                    style={[styles.eventBlockTitle, { color: colors.text }]}
                    numberOfLines={tiny ? 1 : 2}
                  >
                    {event.title}
                  </Text>
                </AnimatedPressable>
              );
            })}

            {/* Current time indicator */}
            {nowTop >= 0 && (
              <View style={[styles.nowLine, { top: nowTop, width: GRID_WIDTH }]}>
                <View style={[styles.nowDot, { backgroundColor: colors.error }]} />
                <View style={[styles.nowLineBar, { backgroundColor: colors.error }]} />
              </View>
            )}
          </View>
        </View>
      </ScrollView>

      {/* Empty week — a quiet note over the grid rather than a blank slate */}
      {weekEventCount === 0 && (
        <View style={styles.emptyOverlay} pointerEvents="none">
          <Ionicons name="calendar-outline" size={30} color={colors.muted} />
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            {hiddenCount > 0
              ? `No events in view — ${hiddenCount} outside ${START_HOUR}:00–${END_HOUR}:00`
              : 'No events this week'}
          </Text>
        </View>
      )}
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
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  navBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
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
    paddingVertical: 6,
    paddingBottom: 8,
  },
  dayHeaderCell: {
    alignItems: 'center',
    gap: 3,
  },
  dayLabel: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
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
    paddingRight: 6,
    alignItems: 'flex-end',
  },
  timeLabel: {
    fontSize: 10,
    fontWeight: '600',
    marginTop: -6,
  },
  columnsContainer: {
    position: 'relative',
  },
  dayColumn: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    borderLeftWidth: StyleSheet.hairlineWidth,
  },
  hourGridLine: {
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  eventBlock: {
    position: 'absolute',
    borderLeftWidth: 2.5,
    borderRadius: 5,
    paddingHorizontal: 3,
    paddingVertical: 2,
    overflow: 'hidden',
  },
  eventBlockTime: {
    fontSize: 9,
    fontWeight: '700',
    lineHeight: 12,
  },
  eventBlockTitle: {
    fontSize: 9,
    fontWeight: '600',
    lineHeight: 11,
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
  emptyOverlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '46%',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 24,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
});
