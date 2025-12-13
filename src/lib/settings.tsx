import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type ChartRange = '1D'|'7D'|'30D';
export type Settings = {
  currency: 'EUR'|'USD'|'GBP';
  numberLocale: 'en-US'|'de-DE';
  density: 'cozy'|'compact';
  defaultRange: ChartRange;
  /** FX rates per 1 EUR (manual stub) */
  fxRates: { USD: number; GBP: number };
};

const DEFAULTS: Settings = {
  currency: 'EUR',
  numberLocale: 'en-US',
  density: 'cozy',
  defaultRange: '7D',
  fxRates: { USD: 1.08, GBP: 0.86 },
};

type Ctx = {
  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => Promise<void>;
  ready: boolean;
};

const SettingsCtx = createContext<Ctx>({ settings: DEFAULTS, updateSettings: async()=>{}, ready:false });

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [ready, setReady] = useState(false);

  useEffect(()=>{ (async()=>{
    try{
      const s = await AsyncStorage.getItem('@settings');
      if (s) setSettings({ ...DEFAULTS, ...(JSON.parse(s) as Settings) });
    } catch {}
    setReady(true);
  })() },[]);

  const updateSettings = async (patch: Partial<Settings>)=>{
    const next = { ...settings, ...patch };
    setSettings(next);
    try { await AsyncStorage.setItem('@settings', JSON.stringify(next)); } catch {}
  };

  const value = useMemo(()=>({ settings, updateSettings, ready }),[settings, ready]);
  return <SettingsCtx.Provider value={value}>{children}</SettingsCtx.Provider>;
}

export function useSettings(){ return useContext(SettingsCtx); }
