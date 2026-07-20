/**
 * WeekViewCalendar — 7-day time-grid that stays legible on a phone.
 *
 * The whole week no longer gets crushed into the screen width (which left each
 * day ~47px wide and made overlapping events unreadable slivers). Instead the
 * grid scrolls horizontally with wide, fixed-width day columns — about 2.5 days
 * visible at once, swipe for the rest. The time gutter stays pinned on the left
 * and the day headers track the horizontal scroll so the two never drift apart.
 *
 * On landing it scrolls to today's column (not always Monday) and to the hour
 * that matters, taps and week-nav give haptic feedback, columns snap into
 * place, and events that fall outside the visible hours are surfaced rather
 * than silently dropped.
 */
import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Dimensions,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { useSettings } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { CollectorsEvent } from '@/data/events';
import { parseEventDate } from '@/lib/calendar';

const SCREEN_WIDTH = Dimensions.get('window').width;
const HOUR_HEIGHT = 64;
const START_HOUR = 7;
const END_HOUR = 23;
const TOTAL_HOURS = END_HOUR - START_HOUR;
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TIME_GUTTER_WIDTH = 52;
// Wide, fixed columns so events stay readable and tappable. ~2.5 days show at
// once; the rest are a swipe away. This is the core fix for the cramped view.
const COL_WIDTH = Math.round((SCREEN_WIDTH - TIME_GUTTER_WIDTH) / 2.5);
const GRID_WIDTH = COL_WIDTH * 7;
const GRID_HEIGHT = TOTAL_HOURS * HOUR_HEIGHT;
// Width the two horizontal scrollers share (everything right of the gutter).
const SCROLLER_WIDTH = SCREEN_WIDTH - TIME_GUTTER_WIDTH;

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
  const headerScrollRef = useRef<ScrollView>(null);
  const gridHScrollRef = useRef<ScrollView>(null);
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

  // Keep the day headers aligned with the grid as it scrolls sideways. The
  // header scroller is not user-draggable; the grid drives it.
  const onGridHorizontalScroll = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      headerScrollRef.current?.scrollTo({
        x: e.nativeEvent.contentOffset.x,
        animated: false,
      });
    },
    [],
  );

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

    // 1. Build raw blocks per day
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
      const height = Math.max(Math.min(durationHrs, TOTAL_HOURS) * HOUR_HEIGHT, 34);
      const startTime = start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      (perDay[dayDiff] ??= []).push({
        event: evt,
        dayIndex: dayDiff,
        topOffset,
        height,
        startTime,
      });
    }

    // 2. Per day, assign each event to a horizontal lane so overlapping events
    //    sit side-by-side instead of stacking on top of each other.
    const out: Block[] = [];
    for (const dayKey of Object.keys(perDay)) {
      const dayEvents = perDay[Number(dayKey)]!.sort((a, b) => a.topOffset - b.topOffset);
      // Greedy lane assignment: for each event, place it in the first lane
      // whose previous event has already ended.
      const laneEnds: number[] = []; // bottom Y of the last event placed in each lane
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
      // Compute the max simultaneous lanes for sizing.
      // For accuracy, recompute per-event laneCount as the max lanes that
      // overlap with it; cheap pass since N is small per day.
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

  // On landing on a week, scroll both axes so its events are actually in view.
  // Vertically: this week's current hour, else the earliest event. Horizontally:
  // today's column (so a Thursday event isn't hidden off to the right). Runs
  // once per distinct week.
  useEffect(() => {
    if (lastScrolledWeek.current === weekStart.getTime()) return;
    lastScrolledWeek.current = weekStart.getTime();

    let targetTop: number | null = null;
    if (isThisWeek && nowHour >= START_HOUR && nowHour < END_HOUR) {
      targetTop = (nowHour - START_HOUR - 1) * HOUR_HEIGHT;
    } else if (blocks.length > 0) {
      targetTop = Math.min(...blocks.map((b) => b.topOffset)) - HOUR_HEIGHT / 2;
    }

    // Horizontal: reveal today (with the prior day peeking for context), or the
    // day of the week's first event; otherwise reset to Monday.
    const focusDay = isThisWeek
      ? nowDayIndex
      : blocks.length > 0
        ? Math.min(...blocks.map((b) => b.dayIndex))
        : 0;
    const maxX = Math.max(0, GRID_WIDTH - SCROLLER_WIDTH);
    const targetX = Math.min(Math.max(0, (focusDay - 0.5) * COL_WIDTH), maxX);

    setTimeout(() => {
      if (targetTop !== null) {
        scrollRef.current?.scrollTo({ y: Math.max(0, targetTop), animated: false });
      }
      gridHScrollRef.current?.scrollTo({ x: targetX, animated: false });
      headerScrollRef.current?.scrollTo({ x: targetX, animated: false });
    }, 80);
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

      {/* Day headers — pinned gutter on the left, cells track the grid scroll */}
      <View style={[styles.dayHeaderRow, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <View style={styles.timeGutter} />
        <ScrollView
          ref={headerScrollRef}
          horizontal
          scrollEnabled={false}
          showsHorizontalScrollIndicator={false}
          style={{ width: SCROLLER_WIDTH }}
        >
          <View style={{ flexDirection: 'row', width: GRID_WIDTH }}>
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
        </ScrollView>
      </View>

      {/* Time grid */}
      <ScrollView ref={scrollRef} style={styles.gridScroll} showsVerticalScrollIndicator={false}>
        <View style={styles.gridContainer}>
          {/* Time labels — pinned, scroll only vertically with the grid */}
          <View style={styles.timeGutter}>
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <View key={i} style={[styles.hourRow, { height: HOUR_HEIGHT }]}>
                <Text style={[styles.timeLabel, { color: colors.muted }]}>
                  {String(START_HOUR + i).padStart(2, '0')}:00
                </Text>
              </View>
            ))}
          </View>

          {/* Day columns scroll horizontally; the gutter above stays put */}
          <ScrollView
            ref={gridHScrollRef}
            horizontal
            showsHorizontalScrollIndicator={false}
            scrollEventThrottle={16}
            onScroll={onGridHorizontalScroll}
            snapToInterval={COL_WIDTH}
            snapToAlignment="start"
            decelerationRate="fast"
            disableIntervalMomentum
            nestedScrollEnabled
            style={{ width: SCROLLER_WIDTH }}
          >
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
                const laneWidth = (COL_WIDTH - 4) / laneCount;
                return (
                  <AnimatedPressable
                    key={event.id}
                    style={[
                      styles.eventBlock,
                      {
                        left: dayIndex * COL_WIDTH + 2 + lane * laneWidth,
                        top: topOffset,
                        height,
                        width: laneWidth - 2,
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
                    <Text style={[styles.eventBlockTime, { color: colors.accent }]} numberOfLines={1}>
                      {startTime}
                    </Text>
                    <Text
                      style={[styles.eventBlockTitle, { color: colors.text }]}
                      numberOfLines={laneCount > 1 ? 2 : 3}
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
          </ScrollView>
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
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  navBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekLabel: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },
  weekMeta: {
    fontSize: 12,
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
    gap: 5,
  },
  dayLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  dayNumberCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayNumber: {
    fontSize: 15,
    fontWeight: '600',
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
    fontSize: 11,
    fontWeight: '500',
    marginTop: -7,
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
    borderLeftWidth: 3,
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 4,
    overflow: 'hidden',
  },
  eventBlockTime: {
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 14,
  },
  eventBlockTitle: {
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 15,
    marginTop: 1,
  },
  nowLine: {
    position: 'absolute',
    left: 0,
    flexDirection: 'row',
    alignItems: 'center',
    zIndex: 10,
  },
  nowDot: {
    width: 9,
    height: 9,
    borderRadius: 4.5,
    marginLeft: -4.5,
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
