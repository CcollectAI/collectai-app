import React, { createContext, useContext, useEffect, useCallback, useMemo, useState, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { collectorsApi } from '@/api/collectorsApi';

export type ChartRange = '1D'|'7D'|'30D';
export type Currency = 'EUR'|'USD'|'JPY'|'GBP'|'KRW'|'AUD'|'CAD';
export type NumberLocale = 'en-US'|'de-DE'|'ja-JP'|'nl-NL'|'ko-KR'|'en-AU';
export type Region = 'americas'|'europe'|'japan'|'korea'|'oceania'|'other';

export type Settings = {
  currency: Currency;
  numberLocale: NumberLocale;
  density: 'cozy'|'compact';
  defaultRange: ChartRange;
  /** FX rates per 1 EUR */
  fxRates: { USD: number; GBP: number; JPY: number; KRW: number; AUD: number; CAD: number };
  /** User region (geolocation opt-in) — drives default currency + market pricing */
  region: Region;
  /** Dark mode toggle */
  isDark: boolean;
  /** Haptic feedback toggle */
  hapticsEnabled: boolean;
  /** Micro-animations toggle */
  animationsEnabled: boolean;
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
  isDark: false,
  hapticsEnabled: true,
  animationsEnabled: true,
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
        setSettings((prev) => ({ ...prev, fxRates: next }));
      }
    } catch {
      // keep existing / default rates on failure
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const s = await AsyncStorage.getItem('@settings');
        if (s) setSettings({ ...DEFAULTS, ...(JSON.parse(s) as Settings) });
      } catch {}
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
      AsyncStorage.setItem('@settings', JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const value = useMemo(() => ({ settings, updateSettings, ready }), [settings, updateSettings, ready]);
  return <SettingsCtx.Provider value={value}>{children}</SettingsCtx.Provider>;
}

export function useSettings(){ return useContext(SettingsCtx); }
