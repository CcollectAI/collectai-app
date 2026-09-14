import React from 'react';
import { render } from '@testing-library/react-native';
import CategoryEventsSection from '../CategoryEventsSection';

const colors = {
  text: '#000',
  muted: '#888',
  card: '#fff',
  border: '#ddd',
  accent: '#81D8D0',
  accentText: '#ffffff',
} as unknown as Parameters<typeof CategoryEventsSection>[0]['colors'];

describe('CategoryEventsSection', () => {
  it('renders nothing when there are no events (section hidden)', () => {
    const { queryByText, toJSON } = render(
      <CategoryEventsSection events={[]} onEventPress={jest.fn()} colors={colors} />,
    );
    // Neither the section title nor any placeholder text should appear.
    expect(queryByText('Upcoming events')).toBeNull();
    expect(queryByText(/No upcoming events/i)).toBeNull();
    expect(toJSON()).toBeNull();
  });

  it('renders the section and event rows when events exist', () => {
    const events = [
      { id: 'e1', title: 'MTG Prerelease', kind: 'meetup' as const, date: '2026-07-20', time: '18:00' },
      { id: 'e2', title: 'Set Drop', kind: 'collection_drop' as const, date: '2026-08-01' },
    ];
    const { getByText } = render(
      <CategoryEventsSection events={events} onEventPress={jest.fn()} colors={colors} />,
    );
    expect(getByText('Upcoming events')).toBeTruthy();
    expect(getByText('MTG Prerelease')).toBeTruthy();
    expect(getByText('Set Drop')).toBeTruthy();
  });

  it('formats the date instead of printing the backend fields (2026-09-14)', () => {
    // Walked on Android: "Convention · 2026-09-17 · 16:00:00" — an ISO date and
    // a seconds-precise time, in the row AND its accessibility label.
    const events = [
      { id: 'e1', title: 'Minnesota Card Show', kind: 'convention' as const, date: '2026-09-17', time: '16:00:00' },
    ];
    const { toJSON, getByLabelText } = render(
      <CategoryEventsSection events={events} onEventPress={jest.fn()} colors={colors} />,
    );
    const rendered = JSON.stringify(toJSON());
    expect(rendered).not.toContain('2026-09-17');
    expect(rendered).not.toContain('16:00:00');
    // Shared label map, not a local copy.
    expect(rendered).toContain('Convention');
    const label = getByLabelText(/Minnesota Card Show, Convention, /);
    expect(label.props.accessibilityLabel).not.toContain('2026-09-17');
    expect(label.props.accessibilityLabel).not.toContain('16:00:00');
  });
});
