/**
 * CalendarGrid — Professional monthly calendar view with event dots.
 * Shows a month grid with navigation. Days with events display colored dots
 * by event kind. Tapping a day filters the event list.
 */

import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, Pressable, StyleSheet, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { CollectorsEvent, EventKind } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

/** Color mapping for event kinds — uses theme info/success/warning/danger colors. */
function getKindDotColor(themeColors: { info: string; success: string; warning: string; danger: string }): Record<EventKind, string> {
  return {
    meetup: themeColors.info,
    collection_drop: themeColors.success,
    release: themeColors.warning,
    stream: themeColors.danger,
    convention: '#A855F7',
  };
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const SCREEN_WIDTH = Dimensions.get('window').width;
const GRID_PADDING = 12;
const CELL_SIZE = Math.floor((SCREEN_WIDTH - 32 - GRID_PADDING * 2) / 7);

interface CalendarGridProps {
  events: CollectorsEvent[];
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
}

function toISO(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function todayISO(): string {
  const d = new Date();
  return toISO(d.getFullYear(), d.getMonth(), d.getDate());
}

function buildMonthGrid(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();

  const cells: {
    day: number;
    month: number;
    year: number;
    iso: string;
    isCurrentMonth: boolean;
  }[] = [];

  const prevMonth = month === 0 ? 11 : month - 1;
  const prevYear = month === 0 ? year - 1 : year;
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrev - i;
    cells.push({ day: d, month: prevMonth, year: prevYear, iso: toISO(prevYear, prevMonth, d), isCurrentMonth: false });
  }

  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, month, year, iso: toISO(year, month, d), isCurrentMonth: true });
  }

  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      cells.push({ day: d, month: nextMonth, year: nextYear, iso: toISO(nextYear, nextMonth, d), isCurrentMonth: false });
    }
  }

  return cells;
}

function CalendarGridInner({ events, selectedDate, onSelectDate }: CalendarGridProps) {
  const { colors } = useAppTheme();
  const KIND_DOT_COLOR = getKindDotColor(colors);
  const today = todayISO();

  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());

  const eventsByDate = useMemo(() => {
    const map: Record<string, EventKind[]> = {};
    for (const evt of events) {
      const dateKey = evt.date.slice(0, 10);
      if (!map[dateKey]) map[dateKey] = [];
      if (!map[dateKey].includes(evt.kind)) {
        map[dateKey].push(evt.kind);
      }
    }
    return map;
  }, [events]);

  const grid = useMemo(() => buildMonthGrid(viewYear, viewMonth), [viewYear, viewMonth]);

  const goToPrev = useCallback(() => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear((y) => y - 1); }
    else { setViewMonth((m) => m - 1); }
  }, [viewMonth]);

  const goToNext = useCallback(() => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear((y) => y + 1); }
    else { setViewMonth((m) => m + 1); }
  }, [viewMonth]);

  const goToToday = useCallback(() => {
    const d = new Date();
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
    onSelectDate(null);
  }, [onSelectDate]);

  const handleDayPress = useCallback(
    (iso: string) => { onSelectDate(selectedDate === iso ? null : iso); },
    [selectedDate, onSelectDate],
  );

  const rows: (typeof grid)[] = [];
  for (let i = 0; i < grid.length; i += 7) {
    rows.push(grid.slice(i, i + 7));
  }

  // Count events this month for the summary
  const monthEventCount = useMemo(() => {
    let count = 0;
    for (const key of Object.keys(eventsByDate)) {
      if (key.startsWith(`${viewYear}-${String(viewMonth + 1).padStart(2, '0')}`)) {
        count += eventsByDate[key].length;
      }
    }
    return count;
  }, [eventsByDate, viewYear, viewMonth]);

  return (
    <View
      style={[styles.container, { backgroundColor: colors.card }]}
      accessibilityRole="none"
      accessibilityLabel="Calendar grid"
    >
      {/* Month header */}
      <View style={styles.header}>
        <AnimatedPressable
          onPress={goToPrev}
          style={[styles.navBtn, { backgroundColor: colors.border + '40' }]}
          accessibilityRole="button"
          accessibilityLabel="Previous month"
        >
          <Ionicons name="chevron-back" size={18} color={colors.text} />
        </AnimatedPressable>

        <Pressable onPress={goToToday} accessibilityRole="button" accessibilityLabel="Go to today">
          <Text style={[styles.monthTitle, { color: colors.text }]}>
            {MONTH_NAMES[viewMonth]} {viewYear}
          </Text>
          {monthEventCount > 0 && (
            <Text style={[styles.monthEventCount, { color: colors.muted }]}>
              {monthEventCount} event{monthEventCount !== 1 ? 's' : ''}
            </Text>
          )}
        </Pressable>

        <AnimatedPressable
          onPress={goToNext}
          style={[styles.navBtn, { backgroundColor: colors.border + '40' }]}
          accessibilityRole="button"
          accessibilityLabel="Next month"
        >
          <Ionicons name="chevron-forward" size={18} color={colors.text} />
        </AnimatedPressable>
      </View>

      {/* Weekday labels */}
      <View style={[styles.weekdayRow, { borderBottomColor: colors.border }]}>
        {WEEKDAY_LABELS.map((label) => (
          <View key={label} style={styles.weekdayCell}>
            <Text style={[
              styles.weekdayText,
              { color: label === 'Sun' || label === 'Sat' ? colors.muted + '80' : colors.muted },
            ]}>
              {label}
            </Text>
          </View>
        ))}
      </View>

      {/* Day grid */}
      {rows.map((row, ri) => (
        <View key={ri} style={styles.dayRow}>
          {row.map((cell) => {
            const isToday = cell.iso === today;
            const isSelected = cell.iso === selectedDate;
            const dots = eventsByDate[cell.iso] || [];
            const hasEvents = dots.length > 0;

            return (
              <Pressable
                key={cell.iso}
                style={[styles.dayCell, { height: CELL_SIZE }]}
                onPress={() => handleDayPress(cell.iso)}
                accessibilityRole="button"
                accessibilityLabel={`${cell.day} ${MONTH_NAMES[cell.month]} ${cell.year}${dots.length ? `, ${dots.length} event${dots.length > 1 ? 's' : ''}` : ''}`}
                accessibilityState={{ selected: isSelected }}
              >
                <View style={[
                  styles.dayCellInner,
                  isToday && !isSelected && [styles.todayHighlight, { borderColor: colors.accent }],
                  isSelected && [styles.selectedHighlight, { backgroundColor: colors.accent }],
                  hasEvents && !isSelected && !isToday && { backgroundColor: colors.accent + '08' },
                ]}>
                  <Text
                    style={[
                      styles.dayText,
                      {
                        color: isSelected
                          ? '#FFFFFF'
                          : !cell.isCurrentMonth
                            ? colors.muted + '40'
                            : isToday
                              ? colors.accent
                              : colors.text,
                      },
                      isToday && { fontWeight: '800' },
                      isSelected && { fontWeight: '700' },
                    ]}
                  >
                    {cell.day}
                  </Text>
                </View>

                {/* Event dots */}
                {hasEvents && (
                  <View style={styles.dotRow}>
                    {dots.slice(0, 3).map((kind) => (
                      <View
                        key={kind}
                        style={[
                          styles.dot,
                          { backgroundColor: isSelected ? '#FFFFFF' : KIND_DOT_COLOR[kind] },
                        ]}
                      />
                    ))}
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>
      ))}

      {/* Legend */}
      <View style={[styles.legend, { borderTopColor: colors.border }]}>
        {(Object.entries(KIND_DOT_COLOR) as [EventKind, string][]).map(([kind, color]) => (
          <View key={kind} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: color }]} />
            <Text style={[styles.legendText, { color: colors.muted }]}>
              {kind.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 20,
    paddingHorizontal: GRID_PADDING,
    paddingTop: 16,
    paddingBottom: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
    marginBottom: 16,
  },
  navBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
  },
  monthTitle: {
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },
  monthEventCount: {
    fontSize: 11,
    fontWeight: '500',
    textAlign: 'center',
    marginTop: 2,
  },
  weekdayRow: {
    flexDirection: 'row',
    marginBottom: 8,
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  weekdayCell: {
    flex: 1,
    alignItems: 'center',
  },
  weekdayText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  dayRow: {
    flexDirection: 'row',
  },
  dayCell: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 1,
  },
  dayCellInner: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  todayHighlight: {
    borderWidth: 2,
  },
  selectedHighlight: {
    shadowColor: '#81D8D0',
    shadowOpacity: 0.4,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  dayText: {
    fontSize: 14,
    fontWeight: '500',
  },
  dotRow: {
    position: 'absolute',
    bottom: 1,
    flexDirection: 'row',
    gap: 2,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    justifyContent: 'center',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  legendText: {
    fontSize: 10,
    fontWeight: '500',
  },
});

export const CalendarGrid = React.memo(CalendarGridInner);
export default CalendarGrid;
