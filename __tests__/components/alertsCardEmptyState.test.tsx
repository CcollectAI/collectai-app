/**
 * AlertsCard — what an EMPTY alerts list is allowed to say.
 *
 * WHY (2026-09-09, found walking the app on Android): the card is fed
 * triggered ALERTS but headed "Watchlist", and its only empty state read
 * "Start Your Watchlist". The account on screen had five watchlist rows, so
 * the card invited a member to start something they already had — and it said
 * exactly the same thing when the fetch had FAILED, which is the house
 * silent-failure shape: an empty array answering a question nobody asked.
 *
 * These tests pin the two honest answers: "we could not ask" and "nothing has
 * fired yet". Neither of them may claim the watchlist is empty.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      card: '#FFFFFF', text: '#0F172A', muted: '#64748B', border: '#E2E8F0',
      accent: '#81D8D0', success: '#10B981', danger: '#EF4444', error: '#EF4444',
      info: '#3B82F6', warning: '#F59E0B', background: '#FFFFFF',
    },
  }),
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, opts?: { defaultValue?: string }) => opts?.defaultValue ?? _key,
  }),
}));

import { AlertsCard } from '../../src/components/home/AlertsCard';

describe('AlertsCard empty state', () => {
  it('says nothing has fired yet — never that the watchlist is empty', () => {
    render(<AlertsCard alerts={[]} />);
    expect(screen.getByText('No alerts yet')).toBeTruthy();
    expect(screen.queryByText(/Start Your Watchlist/i)).toBeNull();
  });

  it('says the fetch failed when it failed, instead of showing the empty copy', () => {
    render(<AlertsCard alerts={[]} failed onRetry={jest.fn()} />);
    expect(screen.getByText("Couldn't load alerts")).toBeTruthy();
    expect(screen.queryByText('No alerts yet')).toBeNull();
    expect(screen.queryByText(/Start Your Watchlist/i)).toBeNull();
  });

  it('retries on tap when it failed, rather than navigating to the watchlist', () => {
    const onRetry = jest.fn();
    const onStartWatchlist = jest.fn();
    render(
      <AlertsCard alerts={[]} failed onRetry={onRetry} onStartWatchlist={onStartWatchlist} />,
    );
    fireEvent.press(screen.getByLabelText('Retry loading alerts'));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onStartWatchlist).not.toHaveBeenCalled();
  });

  it('the accessibility label does not contradict the visible copy', () => {
    // The visible text stopped saying "Start Your Watchlist"; the a11y label
    // did not, so a screen-reader user still heard it. A fix that only lands in
    // the pixels is half a fix.
    render(<AlertsCard alerts={[]} />);
    expect(screen.getByText('No alerts yet')).toBeTruthy();
    expect(screen.queryByLabelText(/Start your watchlist/i)).toBeNull();
    expect(screen.getByLabelText('Open your watchlist')).toBeTruthy();
  });
});
