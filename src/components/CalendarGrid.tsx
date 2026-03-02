/**
 * CalendarGrid — Monthly calendar view with event dots.
 * Shows a month grid with navigation. Days with events display colored dots
 * by event kind. Tapping a day filters the event list. No external deps.
 */

import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { CollectorsEvent, EventKind } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';

/** Color mapping for event kinds — matches the spec colors. */
const KIND_DOT_COLOR: Record<EventKind, string> = {
  meetup: '#3B82F6',        // blue
  collection_drop: '#22C55E', // green (sale-like)
  release: '#F97316',       // orange
  stream: '#EF4444',        // red
  convention: '#A855F7',    // purple (bonus — distinct from the rest)
};

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

interface CalendarGridProps {
  events: CollectorsEvent[];
  selectedDate: string | null;            // ISO "YYYY-MM-DD" or null
  onSelectDate: (date: string | null) => void;
}

/** Build an ISO date string "YYYY-MM-DD" from parts. */
function toISO(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** Get today as ISO string. */
function todayISO(): string {
  const d = new Date();
  return toISO(d.getFullYear(), d.getMonth(), d.getDate());
}

/**
 * Build a 6-row x 7-col grid of day cells for the given month.
 * Each cell: { day, month, year, iso, isCurrentMonth }.
 */
function buildMonthGrid(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();

  const cells: {
    day: number;
    month: number;
    year: number;
    iso: string;
    isCurrentMonth: boolean;
  }[] = [];

  // Previous month trailing days
  const prevMonth = month === 0 ? 11 : month - 1;
  const prevYear = month === 0 ? year - 1 : year;
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrev - i;
    cells.push({
      day: d,
      month: prevMonth,
      year: prevYear,
      iso: toISO(prevYear, prevMonth, d),
      isCurrentMonth: false,
    });
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d,
      month,
      year,
      iso: toISO(year, month, d),
      isCurrentMonth: true,
    });
  }

  // Next month leading days — fill to complete rows of 7
  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      cells.push({
        day: d,
        month: nextMonth,
        year: nextYear,
        iso: toISO(nextYear, nextMonth, d),
        isCurrentMonth: false,
      });
    }
  }

  return cells;
}

export function CalendarGrid({ events, selectedDate, onSelectDate }: CalendarGridProps) {
  const { colors } = useAppTheme();
  const today = todayISO();

  // Navigation state: which month is displayed
  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());

  // Build a map: ISO date -> array of event kinds for that date
  const eventsByDate = useMemo(() => {
    const map: Record<string, EventKind[]> = {};
    for (const evt of events) {
      // evt.date is ISO "YYYY-MM-DD" (possibly with time info stripped)
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
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  }, [viewMonth]);

  const goToNext = useCallback(() => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  }, [viewMonth]);

  const goToToday = useCallback(() => {
    const d = new Date();
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
    onSelectDate(null);
  }, [onSelectDate]);

  const handleDayPress = useCallback(
    (iso: string) => {
      // Toggle: if same date tapped again, deselect
      onSelectDate(selectedDate === iso ? null : iso);
    },
    [selectedDate, onSelectDate],
  );

  // Split grid into rows of 7
  const rows: (typeof grid)[] = [];
  for (let i = 0; i < grid.length; i += 7) {
    rows.push(grid.slice(i, i + 7));
  }

  return (
    <View
      style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="none"
      accessibilityLabel="Calendar grid"
    >
      {/* Month header with navigation */}
      <View style={styles.header}>
        <Pressable
          onPress={goToPrev}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Previous month"
        >
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </Pressable>

        <Pressable onPress={goToToday} accessibilityRole="button" accessibilityLabel="Go to today">
          <Text style={[styles.monthTitle, { color: colors.text }]}>
            {MONTH_NAMES[viewMonth]} {viewYear}
          </Text>
        </Pressable>

        <Pressable
          onPress={goToNext}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Next month"
        >
          <Ionicons name="chevron-forward" size={22} color={colors.text} />
        </Pressable>
      </View>

      {/* Weekday labels */}
      <View style={styles.weekdayRow}>
        {WEEKDAY_LABELS.map((label) => (
          <View key={label} style={styles.weekdayCell}>
            <Text style={[styles.weekdayText, { color: colors.muted }]}>{label}</Text>
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

            return (
              <Pressable
                key={cell.iso}
                style={styles.dayCell}
                onPress={() => handleDayPress(cell.iso)}
                accessibilityRole="button"
                accessibilityLabel={`${cell.day} ${MONTH_NAMES[cell.month]} ${cell.year}${dots.length ? `, ${dots.length} event${dots.length > 1 ? 's' : ''}` : ''}`}
                accessibilityState={{ selected: isSelected }}
              >
                {/* Today circle background */}
                {isToday && !isSelected && (
                  <View
                    style={[
                      styles.todayCircle,
                      { borderColor: colors.accent },
                    ]}
                  />
                )}
                {/* Selected highlight */}
                {isSelected && (
                  <View
                    style={[
                      styles.selectedCircle,
                      { backgroundColor: colors.accent },
                    ]}
                  />
                )}
                <Text
                  style={[
                    styles.dayText,
                    {
                      color: isSelected
                        ? '#FFFFFF'
                        : cell.isCurrentMonth
                          ? colors.text
                          : colors.muted + '60',
                    },
                  ]}
                >
                  {cell.day}
                </Text>

                {/* Event dots (max 3 shown) */}
                {dots.length > 0 && (
                  <View style={styles.dotRow}>
                    {dots.slice(0, 3).map((kind) => (
                      <View
                        key={kind}
                        style={[styles.dot, { backgroundColor: KIND_DOT_COLOR[kind] }]}
                      />
                    ))}
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const CELL_SIZE = 40;

const styles = StyleSheet.create({
  container: {
    borderRadius: 16,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingTop: 12,
    paddingBottom: 8,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    marginBottom: 12,
  },
  monthTitle: {
    fontSize: 16,
    fontWeight: '700',
  },
  weekdayRow: {
    flexDirection: 'row',
    marginBottom: 4,
  },
  weekdayCell: {
    flex: 1,
    alignItems: 'center',
  },
  weekdayText: {
    fontSize: 11,
    fontWeight: '600',
  },
  dayRow: {
    flexDirection: 'row',
  },
  dayCell: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: CELL_SIZE,
    position: 'relative',
  },
  dayText: {
    fontSize: 14,
    fontWeight: '500',
    zIndex: 1,
  },
  todayCircle: {
    position: 'absolute',
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 2,
  },
  selectedCircle: {
    position: 'absolute',
    width: 32,
    height: 32,
    borderRadius: 16,
  },
  dotRow: {
    position: 'absolute',
    bottom: 2,
    flexDirection: 'row',
    gap: 2,
    zIndex: 1,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
  },
});

export default CalendarGrid;
