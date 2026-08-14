-- How experienced a collector says they are, so the app can meet them there.
--
-- Drives two things and nothing else: whether a beginner sees "how to start"
-- surfaces, and which guide depth is offered. It is NOT a gate — no feature is
-- withheld from a beginner, and nothing is hidden from an expert.
--
-- THE TRAP THIS COLUMN IS WALKING INTO
-- ------------------------------------
-- docs/ARCHITECTURE.md, "user_settings: currency / region / locale — code and
-- CHECK must agree": until 2026-07-30 all three CHECKs were missing the values
-- the code already accepted (korea, oceania, KRW, AUD, ko-KR, en-AU). The
-- handler validated a value as legal, the INSERT raised 23514, and the user got
-- a generic 500 — on defaults the app itself had chosen for them. A Korean user
-- could save neither currency, nor region, nor locale.
--
-- So the rule for this column: the CHECK below and `VALID_SKILL_LEVELS` in
-- server/app/routes/user_settings_router.py are ONE contract in two files.
-- Changing either alone reproduces that bug exactly. There is a deliberate
-- pointer in both directions.
--
-- NULL is meaningful and stays allowed: it means "never asked". A member who
-- onboarded before this column existed is not a beginner, and defaulting them
-- to one would show a first-time-collector banner to someone with 400 items.

ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS skill_level text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_settings_skill_level_check'
  ) THEN
    ALTER TABLE public.user_settings
      ADD CONSTRAINT user_settings_skill_level_check
      CHECK (skill_level IS NULL OR skill_level IN ('beginner', 'intermediate', 'advanced'));
  END IF;
END $$;

COMMENT ON COLUMN public.user_settings.skill_level IS
  'beginner | intermediate | advanced, or NULL for "never asked". Must stay in '
  'lockstep with VALID_SKILL_LEVELS in user_settings_router.py — see '
  'docs/ARCHITECTURE.md on currency/region/locale, where the same pair drifted '
  'and produced a 500 on values the app itself had chosen.';
