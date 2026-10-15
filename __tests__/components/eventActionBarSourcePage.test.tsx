/**
 * Imported events link to their own page (2026-10-15).
 *
 * No imported source sets online_url, so the detail screen had no way to the
 * tickets or the store's registration page. The action bar now opens
 * `sourceUrl` ("Event page") when there is no online link.
 */
import React from 'react';
import { Linking } from 'react-native';
import { render, fireEvent } from '@testing-library/react-native';

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { accent: '#81D8D0', accentText: '#fff', card: '#fff', border: '#eee', text: '#000', muted: '#666' } }),
}));
jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return { AnimatedPressable: (props: any) => <Pressable {...props} /> };
});
jest.mock('../../src/haptics', () => ({ fireHaptic: jest.fn(), HapticIntent: { CONFIRMATION_LIGHT: 'x' } }));
jest.mock('../../src/components/Toast', () => ({ useToast: () => ({ showToast: jest.fn() }) }));

import { EventActionBar } from '../../src/components/events/EventActionBar';
import type { CollectorsEvent } from '../../src/data/events';

const base: CollectorsEvent = {
  id: 'e1', title: 'Hyperia City Pre-Release', kind: 'meetup', date: '2026-10-17',
  description: '', attendeeIds: [], source: 'ravensburger_play',
  sourceUrl: 'https://tcg.ravensburgerplay.com/events/886328',
};

describe('EventActionBar — event page', () => {
  beforeEach(() => jest.spyOn(Linking, 'openURL').mockResolvedValue(true));

  it('opens the source page when there is no online link', () => {
    const r = render(<EventActionBar event={base} hapticsEnabled={false} />);
    fireEvent.press(r.getByText('Event page'));
    expect(Linking.openURL).toHaveBeenCalledWith('https://tcg.ravensburgerplay.com/events/886328');
  });

  it('prefers the online link when there is one', () => {
    const r = render(<EventActionBar event={{ ...base, kind: 'stream', onlineUrl: 'https://twitch.tv/x' }} hapticsEnabled={false} />);
    fireEvent.press(r.getByText('Open stream'));
    expect(Linking.openURL).toHaveBeenCalledWith('https://twitch.tv/x');
  });

  it('shows no link without either', () => {
    const r = render(<EventActionBar event={{ ...base, sourceUrl: undefined }} hapticsEnabled={false} />);
    expect(r.queryByText('Event page')).toBeNull();
  });
});
