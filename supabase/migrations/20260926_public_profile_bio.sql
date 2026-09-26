-- Public profile shows the bio (2026-09-26).
--
-- Edit Profile has a "Bio — Tell other collectors about yourself" field, and it
-- saves to profiles.bio. Nothing ever showed it: user_public_profile_v1 had no
-- bio column, so src/data/providers/userProvider.ts mapped `bio: null` and
-- UserCollectionPreview's bio card could never render. Found on the Android
-- walk: saved "Test account for the app walk", the profile showed no bio.
--
-- Exposes nothing new: user_public_profiles (the Find-collectors search view,
-- same DEFINER + same grants) already returns p.bio to the same callers.
-- Body is prod's pg_get_viewdef verbatim with ONE column appended at the end —
-- CREATE OR REPLACE VIEW may only add columns after the existing ones — so
-- grants, owner and the privacy CASEs are untouched.
--
-- Falsifier: select bio from public.user_public_profile_v1
--            where user_id = '03d1b2fd-33bd-4168-95a0-f63c23136353';
--            expect 'Test account for the app walk'.

-- rls-ok: PUBLIC on purpose — how one collector sees another. Same body as
-- 20260804_privacy_settings_enforcement (privacy CASEs gate count and value);
-- bio is text the member wrote for other collectors to read.
CREATE OR REPLACE VIEW public.user_public_profile_v1 AS
 SELECT id AS user_id,
    COALESCE(display_name, username) AS display_handle,
    avatar_url,
    created_at,
    created_at AS updated_at,
        CASE
            WHEN COALESCE(( SELECT ps.show_item_count
               FROM user_privacy_settings ps
              WHERE (ps.user_id = p.id)), true) THEN ( SELECT count(*) AS count
               FROM items i
              WHERE ((i.user_id = p.id) AND (COALESCE(i.archived, false) = false)))
            ELSE NULL::bigint
        END AS collection_count,
        CASE
            WHEN COALESCE(( SELECT ps.show_collection_value
               FROM user_privacy_settings ps
              WHERE (ps.user_id = p.id)), true) THEN ( SELECT round((COALESCE(sum(COALESCE((( SELECT pp.q50
                       FROM price_predictions pp
                      WHERE (pp.item_ref = i.canonical_ref)
                      ORDER BY pp.generated_at DESC
                     LIMIT 1))::double precision, (( SELECT qp.q50_eur
                       FROM quick_predictions qp
                      WHERE (qp.item_id = i.id)
                      ORDER BY qp.created_at DESC
                     LIMIT 1))::double precision, i.predicted_price_eur, (i.estimated_value)::double precision, (0)::double precision)), (0)::double precision))::numeric, 2) AS round
               FROM items i
              WHERE ((i.user_id = p.id) AND (COALESCE(i.archived, false) = false)))
            ELSE NULL::numeric
        END AS collection_value_eur,
    p.bio
   FROM profiles p
  WHERE (COALESCE(NULLIF(display_name, ''::text), NULLIF(username, ''::text)) IS NOT NULL);
