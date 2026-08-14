import React, { createContext, useContext, useEffect, useCallback, useMemo, useState, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { collectorsApi } from '@/api/collectorsApi';
import { updateFxCache, getFxRates } from '@/lib/fx';
import type { CurrencyCode } from '@/data/types';
import logger from '@/utils/logger';
import i18n, { SUPPORTED_LOCALES, type SupportedLocale } from '@/i18n';
import { setActiveNumberLocale } from '@/lib/format';

export type ChartRange = '1D'|'7D'|'30D';
/** @deprecated Use CurrencyCode from '@/data/types' for new code */
export type Currency = CurrencyCode;
export type NumberLocale = 'en-US'|'de-DE'|'ja-JP'|'nl-NL'|'ko-KR'|'en-AU';
export type Region = 'americas'|'europe'|'japan'|'korea'|'oceania'|'other';
/** Must match VALID_SKILL_LEVELS (user_settings_router.py) and the CHECK in
 *  migration 20260814c — one contract, three files. */
export type SkillLevel = 'beginner' | 'intermediate' | 'advanced';
/** UI language override. 'auto' = use device locale (detected at app boot). */
export type LanguagePreference = 'auto' | SupportedLocale;

export type Settings = {
  currency: Currency;
  numberLocale: NumberLocale;
  density: 'cozy'|'compact';
  defaultRange: ChartRange;
  /** FX rates per 1 EUR */
  fxRates: { USD: number; GBP: number; JPY: number; KRW: number; AUD: number; CAD: number };
  /** User region (geolocation opt-in) — drives default currency + market pricing */
  region: Region;
  /**
   * How experienced the member says they are. `null` means NEVER ASKED, which
   * is not the same as 'beginner' — someone who onboarded before this existed
   * must not be shown first-time-collector surfaces. Read it as a tri-state.
   */
  skillLevel: SkillLevel | null;
  /** Dark mode toggle */
  isDark: boolean;
  /** Haptic feedback toggle */
  hapticsEnabled: boolean;
  /** Micro-animations toggle */
  animationsEnabled: boolean;
  /** UI language override (auto = device locale) */
  language: LanguagePreference;
};

/** Map region to default currency + locale */
export const REGION_DEFAULTS: Record<Region, { currency: Currency; numberLocale: NumberLocale }> = {
  americas: { currency: 'USD', numberLocale: 'en-US' },
  europe:   { currency: 'EUR', numberLocale: 'de-DE' },
  japan:    { currency: 'JPY', numberLocale: 'ja-JP' },
  korea:    { currency: 'KRW', numberLocale: 'ko-KR' },
  oceania:  { currency: 'AUD', numberLocale: 'en-AU' },
  other:    { currency: 'EUR', numberLocale: 'en-US' },
};

const DEFAULTS: Settings = {
  currency: 'EUR',
  numberLocale: 'de-DE',
  density: 'cozy',
  defaultRange: '7D',
  fxRates: { USD: 1.08, GBP: 0.86, JPY: 164.0, KRW: 1490, AUD: 1.67, CAD: 1.52 },
  region: 'europe',
  skillLevel: null,
  isDark: false,
  hapticsEnabled: true,
  animationsEnabled: true,
  language: 'auto',
};

type Ctx = {
  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => void;
  ready: boolean;
};

const SettingsCtx = createContext<Ctx>({ settings: DEFAULTS, updateSettings: ()=>{}, ready:false });

const FX_REFRESH_MS = 8 * 60 * 60 * 1000; // 8 hours

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [ready, setReady] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchFxRates = useCallback(async () => {
    try {
      const data = await collectorsApi.getFxRates();
      if (data?.rates_from_eur) {
        const r = data.rates_from_eur;
        const next: Settings['fxRates'] = {
          USD: r.USD ?? DEFAULTS.fxRates.USD,
          GBP: r.GBP ?? DEFAULTS.fxRates.GBP,
          JPY: r.JPY ?? DEFAULTS.fxRates.JPY,
          KRW: r.KRW ?? DEFAULTS.fxRates.KRW,
          AUD: r.AUD ?? DEFAULTS.fxRates.AUD,
          CAD: r.CAD ?? DEFAULTS.fxRates.CAD,
        };
        updateFxCache(next);
        setSettings((prev) => ({ ...prev, fxRates: next }));
      }
    } catch (e) {
      logger.error('[settings] FX rate fetch failed:', e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const s = await AsyncStorage.getItem('@settings');
        if (s) {
          const parsed = { ...DEFAULTS, ...(JSON.parse(s) as Settings) };
          setSettings(parsed);
          // Apply persisted language override to i18n so subsequent renders use it.
          if (parsed.language && parsed.language !== 'auto') {
            i18n.changeLanguage(parsed.language).catch((e) =>
              logger.warn('[settings] i18n.changeLanguage failed:', e),
            );
          }
        }
      } catch (e) {
        logger.error('[settings] Failed to load settings from AsyncStorage:', e);
      }
      setReady(true);
    })();

    // Fetch live FX rates on boot + every hour
    fetchFxRates();
    intervalRef.current = setInterval(fetchFxRates, FX_REFRESH_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchFxRates]);

  const updateSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      // Persist async (fire and forget)
      AsyncStorage.setItem('@settings', JSON.stringify(next)).catch((e) => {
        logger.warn('[settings] Failed to persist settings:', e);
      });
      // Apply language change to i18n (auto = revert to device detection = fallback)
      if (patch.language !== undefined) {
        const target =
          patch.language === 'auto'
            ? 'en' // fallback when auto is chosen after an override; device detection ran at boot
            : patch.language;
        // Only switch if supported (safety — type already enforces this)
        if (SUPPORTED_LOCALES.includes(target as SupportedLocale)) {
          i18n.changeLanguage(target).catch((e) =>
            logger.warn('[settings] i18n.changeLanguage failed:', e),
          );
        }
      }
      return next;
    });
  }, []);

  // Publish the user's chosen number locale to the formatters.
  //
  // NOT derived from the UI language. docs/ARCHITECTURE.md is explicit —
  // "`user_settings.locale` is the number-format locale. The UI language is a
  // different set (en,nl,de,fr,es,ja,ko). Don't merge them." The column is also
  // CHECK-constrained to exactly six NumberLocale values, so deriving fr-FR or
  // es-ES from a French or Spanish UI would 23514 on save and hand the user the
  // generic 500 that section already documents happening to Korean users.
  //
  // What this fixes instead: 148 of the 164 formatPrice call sites pass no
  // locale, so they fell through to CURRENCY_LOCALE — nl-NL for EUR — and
  // ignored the user's setting entirely. Now they follow it.
  useEffect(() => {
    setActiveNumberLocale(settings.numberLocale ?? null);
  }, [settings.numberLocale]);

  const value = useMemo(() => ({ settings, updateSettings, ready }), [settings, updateSettings, ready]);
  return <SettingsCtx.Provider value={value}>{children}</SettingsCtx.Provider>;
}

export function useSettings(){ return useContext(SettingsCtx); }

/**
 * Non-React read of the user's settings.
 *
 * `useSettings` is a Context hook, so modules that run outside the React tree
 * — data providers, background tasks, market adapters — cannot reach it. That
 * gap had a real cost: watchlistProvider's "I Got It!" posted a purchase_price
 * with no purchase_currency because it had no way to ask, so a non-EUR user's
 * amount was recorded as if it were EUR.
 *
 * Same escape hatch `src/lib/fx.ts` already uses for rates. `updateSettings`
 * persists to AsyncStorage on every change, so the stored blob is the current
 * user choice; merge it over DEFAULTS exactly as the provider's boot path does.
 *
 * `fxRates` is taken from the live module cache rather than the persisted blob:
 * `fetchFxRates` refreshes rates via setSettings + updateFxCache and never
 * writes them back to AsyncStorage, so the stored copy is stale by design.
 */
export async function getSettingsSnapshot(): Promise<Settings> {
  let stored: Partial<Settings> = {};
  try {
    const s = await AsyncStorage.getItem('@settings');
    if (s) stored = JSON.parse(s) as Partial<Settings>;
  } catch (e) {
    logger.error('[settings] getSettingsSnapshot read failed, using defaults:', e);
  }
  return { ...DEFAULTS, ...stored, fxRates: getFxRates() };
}
