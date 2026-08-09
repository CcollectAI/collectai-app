-- Widen user_settings.region and .locale to cover Korea and Oceania.
--
-- Same defect as 20260730_user_settings_currency_seven.sql, on the same table
-- and the same endpoint: Korea + Oceania support was added throughout the code
-- and the CHECK constraints were never migrated with it.
--
--   region  CHECK had 4: americas, europe, japan, other
--           code has  6: + korea, oceania      (VALID_REGIONS, REGION_DEFAULTS,
--                                               src/lib/settings.tsx Region)
--   locale  CHECK had 4: en-US, de-DE, ja-JP, nl-NL
--           code has  6: + ko-KR, en-AU        (VALID_LOCALES, NumberLocale)
--
-- `user_settings.locale` is the NUMBER-FORMAT locale (NumberLocale), not the UI
-- language — that is SUPPORTED_LOCALES in src/i18n/index.ts
-- ('en','nl','de','fr','es','ja','ko') and is a different set. Do not merge them.
--
-- Effect before this migration: the handler validated the value as legal, the
-- INSERT raised 23514, and the user got a generic 500 DB_ERROR. Verified on prod
-- 2026-07-30 via PUT /settings:
--   region americas/europe/japan/other -> 200 ; korea, oceania  -> 500
--   locale en-US/de-DE/ja-JP/nl-NL     -> 200 ; ko-KR, en-AU    -> 500
--
-- Combined with the currency defect, a Korean user could not save their
-- currency (KRW), region (korea) OR locale (ko-KR) — and REGION_DEFAULTS hands
-- them exactly those three on first launch. Same for Oceania (AUD/oceania/en-AU).
--
-- Safe to apply: user_settings held 2 rows, both europe/de-DE.

BEGIN;

ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_region_check;

ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_region_check
  CHECK (region = ANY (ARRAY[
    'americas'::text, 'europe'::text, 'japan'::text,
    'korea'::text, 'oceania'::text, 'other'::text
  ]));

ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_locale_check;

ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_locale_check
  CHECK (locale = ANY (ARRAY[
    'en-US'::text, 'de-DE'::text, 'ja-JP'::text,
    'nl-NL'::text, 'ko-KR'::text, 'en-AU'::text
  ]));

COMMIT;
