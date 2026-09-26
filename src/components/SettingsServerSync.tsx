/**
 * Restores a member's saved settings from the server on sign-in (2026-09-26).
 *
 * Settings live in AsyncStorage, and every change is ALSO written to the server
 * (`updateUserSettings`) — but nothing ever read the server copy back. A new
 * install or a second phone started on the local defaults: simcheck, saved as
 * USD, reopened in EUR after a reinstall, while server-written notifications
 * (member_money) kept using USD. The server copy is the member's last
 * deliberate choice, so it wins — but only when the server says a row was
 * SAVED (its defaults for an unsaved member are not a choice).
 *
 * Renders nothing. Inside AuthProvider (it needs the user) and inside
 * SettingsProvider (it writes settings) — see app/_layout.tsx.
 */
import { useEffect, useRef } from 'react';
import { useAuthContext } from '@/providers/useAuthContext';
import { useSettings, REGION_DEFAULTS, type Settings } from '@/lib/settings';
import { getUserSettings } from '@/api/settingsApi';
import { logger } from '@/lib/logger';

const CURRENCIES = new Set(['EUR', 'USD', 'GBP', 'JPY', 'KRW', 'AUD', 'CAD']);
const REGIONS = new Set(Object.keys(REGION_DEFAULTS));
const LOCALES = new Set(['en-US', 'de-DE', 'ja-JP', 'nl-NL', 'ko-KR', 'en-AU']);
const SKILLS = new Set(['beginner', 'intermediate', 'advanced']);

/** Pure: which local settings the server's saved copy changes. Exported for tests. */
export function settingsFromServer(
  server: { currency?: string; region?: string; locale?: string; skill_level?: string | null; saved?: boolean } | null,
  local: Pick<Settings, 'currency' | 'region' | 'numberLocale' | 'skillLevel'>,
): Partial<Settings> {
  if (!server?.saved) return {};
  const patch: Partial<Settings> = {};
  if (server.currency && CURRENCIES.has(server.currency) && server.currency !== local.currency) {
    patch.currency = server.currency as Settings['currency'];
  }
  if (server.region && REGIONS.has(server.region) && server.region !== local.region) {
    patch.region = server.region as Settings['region'];
  }
  if (server.locale && LOCALES.has(server.locale) && server.locale !== local.numberLocale) {
    patch.numberLocale = server.locale as Settings['numberLocale'];
  }
  if (server.skill_level && SKILLS.has(server.skill_level) && server.skill_level !== local.skillLevel) {
    patch.skillLevel = server.skill_level as Settings['skillLevel'];
  }
  return patch;
}

export function SettingsServerSync() {
  const { user } = useAuthContext();
  const { settings, updateSettings, ready } = useSettings();
  const doneFor = useRef<string | null>(null);
  const userId = user?.id ?? null;

  useEffect(() => {
    // After the LOCAL blob has loaded: restoring first would be overwritten
    // by SettingsProvider's AsyncStorage load landing afterwards.
    if (!ready || !userId || doneFor.current === userId) return;
    doneFor.current = userId;
    getUserSettings()
      .then((server) => {
        const patch = settingsFromServer(server, settings);
        if (Object.keys(patch).length) updateSettings(patch);
      })
      .catch((e: unknown) => {
        doneFor.current = null; // try again on the next sign-in/remount
        logger.error('[settings] restoring saved settings failed:', e);
      });
    // settings is read at the moment of sign-in on purpose; later local
    // changes are the member's own and must not re-trigger a restore.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, ready]);

  return null;
}
