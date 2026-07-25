/**
 * i18n Configuration
 *
 * CollectAI uses i18next + react-i18next for internationalization.
 * Device locale is detected via expo-localization and matched against
 * our supported languages. Falls back to English.
 *
 * Supported locales (matches the 7 supported currencies):
 *   - en (English)     — source of truth
 *   - nl (Dutch)       — home market
 *   - de (German)
 *   - fr (French)
 *   - es (Spanish)
 *   - ja (Japanese)
 *   - ko (Korean)
 *
 * Adding a new locale:
 *   1. Create src/i18n/locales/<code>.json mirroring en.json structure
 *   2. Add the code to SUPPORTED_LOCALES below
 *   3. Import and register in `resources` below
 *
 * Usage in components:
 *   import { useTranslation } from 'react-i18next';
 *   const { t } = useTranslation();
 *   <Text>{t('auth.sign_in')}</Text>
 *
 * Usage outside components:
 *   import i18n from '@/i18n';
 *   const label = i18n.t('common.save');
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { getLocales } from 'expo-localization';

import en from './locales/en.json';
import nl from './locales/nl.json';
import de from './locales/de.json';
import fr from './locales/fr.json';
import es from './locales/es.json';
import ja from './locales/ja.json';
import ko from './locales/ko.json';

export const SUPPORTED_LOCALES = ['en', 'nl', 'de', 'fr', 'es', 'ja', 'ko'] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

const resources = {
  en: { translation: en },
  nl: { translation: nl },
  de: { translation: de },
  fr: { translation: fr },
  es: { translation: es },
  ja: { translation: ja },
  ko: { translation: ko },
} as const;

/**
 * Detect the user's device locale and return a supported language code.
 * Falls back to 'en' if no match.
 */
// Retained for the moment i18n is switched back on — see LAUNCH_LOCALE below.
export function detectInitialLocale(): SupportedLocale {
  try {
    const locales = getLocales();
    if (locales && locales.length > 0) {
      // Try each device locale in preference order
      for (const locale of locales) {
        const code = (locale.languageCode || '').toLowerCase();
        if (SUPPORTED_LOCALES.includes(code as SupportedLocale)) {
          return code as SupportedLocale;
        }
      }
    }
  } catch {
    // expo-localization can throw on unusual devices — fall through to default
  }
  return 'en';
}

// ── English-only at launch (2026-07-25) ────────────────────────────────────
// `lng` is pinned to 'en' rather than detected from the device.
//
// The six non-English locales are 168 keys behind en.json (423 vs 591), and a
// separate 608 hardcoded strings across 171 files were never wrapped in t() at
// all. With device detection on, a Dutch or German phone therefore rendered a
// HALF-translated app: wrapped-and-translated strings in the device language,
// everything else in English. Mixed-language UI reads as unfinished in a way
// that plain English does not, and this is a product people pay for.
//
// Nothing here is deleted: detectInitialLocale, the seven locale files and the
// t() call sites all stay. Flipping back is this one line, once the key deficit
// is closed and the 608 strings are wrapped — and preferably once a native
// speaker has checked ja/ko, where machine-translated collector terminology
// ("graded", "sealed", "slabbed") goes wrong in credibility-damaging ways.
const LAUNCH_LOCALE: SupportedLocale = 'en';

i18n.use(initReactI18next).init({
  resources,
  lng: LAUNCH_LOCALE,
  fallbackLng: 'en',
  compatibilityJSON: 'v4', // for React Native < 0.72 with Intl polyfill gaps
  interpolation: {
    escapeValue: false, // React Native already escapes
  },
  // React-i18next specific
  react: {
    useSuspense: false, // Avoid Suspense issues in RN
  },
});

export default i18n;
