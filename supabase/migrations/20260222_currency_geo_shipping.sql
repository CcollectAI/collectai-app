-- Currency, Geolocation & Cross-Border Shipping schema changes
-- Adds KRW/AUD/CAD currencies, korea/oceania regions, shipping columns on market_hits

BEGIN;

-- 1. Widen user_settings.currency CHECK to add KRW, AUD, CAD
ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_currency_check;
ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_currency_check
  CHECK (currency IN ('EUR','USD','JPY','GBP','KRW','AUD','CAD'));

-- 2. Widen user_settings.region CHECK to add korea, oceania
ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_region_check;
ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_region_check
  CHECK (region IN ('americas','europe','japan','korea','oceania','other'));

-- 3. Widen user_settings.locale CHECK to add ko-KR, en-AU
ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_locale_check;
ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_locale_check
  CHECK (locale IN ('en-US','de-DE','ja-JP','nl-NL','ko-KR','en-AU'));

-- 4. Add auto_detected_region to user_settings
ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS auto_detected_region TEXT;

-- 5. Add shipping columns to market_hits
ALTER TABLE public.market_hits
  ADD COLUMN IF NOT EXISTS ships_from TEXT;

ALTER TABLE public.market_hits
  ADD COLUMN IF NOT EXISTS domestic_only BOOLEAN DEFAULT false;

-- shipping column already exists on market_hits, no action needed

COMMIT;
