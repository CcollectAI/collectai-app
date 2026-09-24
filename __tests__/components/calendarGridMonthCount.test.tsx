/**
 * The month summary counts EVENTS, not the kinds of event on each day.
 *
 * 2026-09-24, walked on Android: September read "8 events" while the feed held
 * 20. The count summed the per-day list of distinct kinds (one dot per kind),
 * so several conventions on one day counted as one.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: () => null,
}));

import { CalendarGrid } from '@/components/CalendarGrid';
import type { CollectorsEvent } from '@/data/events';

const now = new Date();
const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
const ev = (id: string, day: string, kind: CollectorsEvent['kind']) =>
  ({ id, title: id, date: `${ym}-${day}`, kind }) as unknown as CollectorsEvent;

it('counts three same-kind events on one day as three', () => {
  render(
    <CalendarGrid
      events={[ev('a', '15', 'convention'), ev('b', '15', 'convention'), ev('c', '15', 'convention'), ev('d', '16', 'meetup')]}
      selectedDate={null}
      onSelectDate={() => {}}
    />,
  );
  expect(screen.getAllByText('4 events').length).toBe(1);
});
