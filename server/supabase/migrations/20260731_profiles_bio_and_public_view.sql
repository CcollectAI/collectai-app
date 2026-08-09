-- Give Settings → Edit Profile somewhere to write, and somewhere to be read from.
--
-- Found 2026-07-31: `ProfileEditSection` is mounted and ungated, and saving
-- calls `PATCH /settings/profile` — a route that did not exist (404). `bio` had
-- nowhere to land either: `profiles` had no such column, and both public views
-- hardcoded `NULL::text AS bio`. So the whole edit-profile feature was live UI
-- over nothing.
--
-- This migration covers the storage half; the route is added in
-- server/app/routes/user_settings_router.py.
--
-- `bio` is capped at 300 characters. The edit form is a short "about you" field,
-- and an unbounded public TEXT column is an abuse surface. The CHECK is the
-- authority — the API validates the same number so the user gets a clear 400
-- instead of a 23514 surfaced as a 500 (the exact failure mode that broke
-- currency/region/locale for Korea and Oceania, see 20260730_*).

BEGIN;

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS bio text;

ALTER TABLE public.profiles
  DROP CONSTRAINT IF EXISTS profiles_bio_length_check;

ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_bio_length_check
  CHECK (bio IS NULL OR char_length(bio) <= 300);

-- Surface it publicly. `user_public_profiles` previously returned
-- `NULL::text AS bio`, so PublicUserProfileCard and UserCollectionPreview —
-- both of which already render `{profile.bio && …}` — could never show one.
--
-- `location` and `interests` stay NULL placeholders: neither has a column, and
-- neither is captured anywhere in the app. Do not wire them up here without a
-- writer, or this repeats.
CREATE OR REPLACE VIEW public.user_public_profiles AS
SELECT
    p.id,
    p.id AS user_id,
    p.username AS handle,
    COALESCE(p.display_name, p.username) AS display_name,
    p.avatar_url,
    p.bio,
    NULL::text AS location,
    NULL::text[] AS interests,
    p.created_at
FROM public.profiles p
WHERE COALESCE(NULLIF(p.display_name, ''::text), NULLIF(p.username, ''::text)) IS NOT NULL;

COMMIT;
