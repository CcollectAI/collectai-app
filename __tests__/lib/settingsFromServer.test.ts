/**
 * A reinstall restores the member's saved settings (2026-09-26): simcheck,
 * saved as USD, reopened in EUR because nothing read the server copy back.
 */
jest.mock('../../src/providers/useAuthContext', () => ({ useAuthContext: () => ({ user: null }) }));
import { settingsFromServer, detectedRegionWrite, CURRENCIES, REGIONS, LOCALES, SKILLS } from '../../src/components/SettingsServerSync';
import * as fs from 'fs';
import * as path from 'path';

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

it("onboarding's detected region never overwrites a saved one; a picked region does", () => {
  expect(detectedRegionWrite(false, { saved: true })).toBe('none');
  expect(detectedRegionWrite(false, { saved: false })).toBe('local+server');
  expect(detectedRegionWrite(false, 'unknown')).toBe('local');
  expect(detectedRegionWrite(true, { saved: true })).toBe('local+server');
});

it("the app's value sets equal the server's VALID_* sets (no silent drop, no 400)", () => {
  const src = fs.readFileSync(path.join(__dirname, '../../server/app/routes/user_settings_router.py'), 'utf8');
  const serverSet = (name: string) => {
    const m = src.match(new RegExp(`^${name}\\s*=\\s*\\{([^}]*)\\}`, 'm'));
    if (!m) throw new Error(`${name} not found in user_settings_router.py`);
    return [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]).sort();
  };
  expect([...CURRENCIES].sort()).toEqual(serverSet('VALID_CURRENCIES'));
  expect([...REGIONS].sort()).toEqual(serverSet('VALID_REGIONS'));
  expect([...LOCALES].sort()).toEqual(serverSet('VALID_LOCALES'));
  expect([...SKILLS].sort()).toEqual(serverSet('VALID_SKILL_LEVELS'));
});
