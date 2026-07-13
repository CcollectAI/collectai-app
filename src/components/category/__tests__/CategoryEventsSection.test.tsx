import React from 'react';
import { render } from '@testing-library/react-native';
import CategoryEventsSection from '../CategoryEventsSection';

const colors = {
  text: '#000',
  muted: '#888',
  card: '#fff',
  border: '#ddd',
  accent: '#81D8D0',
} as unknown as Parameters<typeof CategoryEventsSection>[0]['colors'];

describe('CategoryEventsSection', () => {
  it('renders nothing when there are no events (section hidden)', () => {
    const { queryByText, toJSON } = render(
      <CategoryEventsSection events={[]} onEventPress={jest.fn()} colors={colors} />,
    );
    // Neither the section title nor any placeholder text should appear.
    expect(queryByText('Upcoming Events & Drops')).toBeNull();
    expect(queryByText(/No upcoming events/i)).toBeNull();
    expect(toJSON()).toBeNull();
  });

  it('renders the section and event rows when events exist', () => {
    const events = [
      { id: 'e1', title: 'MTG Prerelease', kind: 'meetup', date: '2026-07-20', time: '18:00' },
      { id: 'e2', title: 'Set Drop', kind: 'collection_drop', date: '2026-08-01' },
    ];
    const { getByText } = render(
      <CategoryEventsSection events={events} onEventPress={jest.fn()} colors={colors} />,
    );
    expect(getByText('Upcoming Events & Drops')).toBeTruthy();
    expect(getByText('MTG Prerelease')).toBeTruthy();
    expect(getByText('Set Drop')).toBeTruthy();
  });
});
