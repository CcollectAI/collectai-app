/**
 * A reinstall restores the member's saved settings (2026-09-26): simcheck,
 * saved as USD, reopened in EUR because nothing read the server copy back.
 */
jest.mock('../../src/providers/useAuthContext', () => ({ useAuthContext: () => ({ user: null }) }));
import { settingsFromServer } from '../../src/components/SettingsServerSync';

const local = { currency: 'EUR', region: 'europe', numberLocale: 'de-DE', skillLevel: null } as const;

it('applies a SAVED server copy', () => {
  expect(settingsFromServer({ currency: 'USD', region: 'americas', locale: 'en-US', skill_level: 'advanced', saved: true }, local as never))
    .toEqual({ currency: 'USD', region: 'americas', numberLocale: 'en-US', skillLevel: 'advanced' });
});

it('ignores an unsaved copy — those are server defaults, not a choice', () => {
  expect(settingsFromServer({ currency: 'USD', region: 'americas', locale: 'en-US', skill_level: null, saved: false }, local as never)).toEqual({});
});

it('ignores values the app does not know, and what already matches', () => {
  expect(settingsFromServer({ currency: 'CHF', region: 'europe', locale: 'fr-CH', skill_level: 'guru', saved: true }, local as never)).toEqual({});
});
