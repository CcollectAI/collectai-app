import React, { createContext, useContext, useEffect, useState } from 'react';
import { Appearance } from 'react-native';
import { get, put } from '../../lib/store';
import type { Category } from '../../types/category';

type Settings = {
  theme: 'light'|'dark'|'system';
  defaultGrid: boolean;
  defaultSortBy: 'created_at'|'latest_price'|'title';
  defaultSortDir: 'asc'|'desc';
  pinnedCategories: Category[];
};

const DEFAULT: Settings = {
  theme: 'system',
  defaultGrid: false,
  defaultSortBy: 'created_at',
  defaultSortDir: 'desc',
  pinnedCategories: [],
};

type Ctx = {
  settings: Settings;
  setSettings: (s: Partial<Settings>) => Promise<void>;
  resolvedTheme: 'light'|'dark';
};

const C = createContext<Ctx>({ settings: DEFAULT, setSettings: async()=>{}, resolvedTheme: 'light' });
export const useSettings = () => useContext(C);

export default function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, _set] = useState<Settings>(DEFAULT);

  useEffect(() => { (async ()=>{
    _set(await get<Settings>('settings', DEFAULT));
  })(); }, []);

  async function setSettings(p: Partial<Settings>) {
    const next = { ...settings, ...p };
    _set(next);
    await put('settings', next);
  }

  const colorScheme = Appearance.getColorScheme();
  const resolvedTheme = settings.theme === 'system' ? (colorScheme ?? 'light') : settings.theme;

  return <C.Provider value={{ settings, setSettings, resolvedTheme }}>{children}</C.Provider>;
}
