-- Enforce user_privacy_settings. Until now the table had ZERO readers.
--
-- ⚠️ DEPLOY ORDER — this migration ADDS COLUMNS to two views that
-- scripts/schema.lock.json tracks (user_public_profiles,
-- user_public_profile_v1). Applying it stales the lock, and the next bake
-- restart runs preflight_schema_lock and HARD-DOWNS THE API. Sequence:
--
--   1. apply this migration
--   2. python3 scripts/regen_schema_lock.py     (reads the live DB)
--   3. server/scripts/verify_privacy_enforcement.py   (expect 13/13)
--   4. only then restart collectai-bake.service
--
--
-- The four toggles in Settings → Privacy wrote to `user_privacy_settings`
-- correctly and nothing ever consulted the result:
--
--   show_collection_value  the profile hardcoded collectionValueEur: null
--   show_item_count        the profile hardcoded collectionCount: null
--   allow_discovery        no search query filtered on it
--   show_online_status     PresenceIndicator rendered presence for any userId
--                          with no check at all — this one FAILED OPEN, since
--                          the column defaults to false but status showed anyway
--
-- Enforcement lives in the DB, not the client. `rpc_get_presence_v1` is
-- SECURITY DEFINER (it bypasses RLS by design so one user can see another's
-- dot), and the profile views are read directly by the app over PostgREST.
-- A check in React would be advisory only — anyone can call the RPC.
--
-- ⚠️ RLS interaction: user_privacy_settings has owner-only SELECT policies.
-- These views must therefore NOT be security_invoker — a non-invoker view
-- evaluates the underlying RLS as the view OWNER, so it can see every row.
-- If one of these is ever recreated WITH (security_invoker = true), the
-- subqueries below return NULL for other users, COALESCE supplies the
-- permissive default, and every gate silently opens. Postgres defaults
-- security_invoker to false; the asserts in the companion test pin it.

-- ---------------------------------------------------------------------------
-- 1. Presence — gate on show_online_status (default FALSE)
-- ---------------------------------------------------------------------------
-- Defaulting to false for users with no settings row matches both the column
-- default and the client's default. You always see your own status.

CREATE OR REPLACE FUNCTION public.rpc_get_presence_v1(p_user_id uuid)
 RETURNS TABLE(user_id uuid, last_seen_at timestamp with time zone, is_online boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    -- Consider offline if last heartbeat > 2 minutes ago
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = p_user_id
    AND (
      up.user_id = auth.uid()
      OR COALESCE(
           (SELECT ps.show_online_status
              FROM user_privacy_settings ps
             WHERE ps.user_id = up.user_id),
           false)
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_get_batch_presence_v1(p_user_ids uuid[])
 RETURNS TABLE(user_id uuid, last_seen_at timestamp with time zone, is_online boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = ANY(p_user_ids)
    AND (
      up.user_id = auth.uid()
      OR COALESCE(
           (SELECT ps.show_online_status
              FROM user_privacy_settings ps
             WHERE ps.user_id = up.user_id),
           false)
    );
END;
$function$;

-- ---------------------------------------------------------------------------
-- 2. Profile stats — populate them, gated (both default TRUE)
-- ---------------------------------------------------------------------------
-- Same value expression as /portfolio/overview: q50 → quick prediction →
-- predicted_price_eur → estimated_value → 0. Kept identical so a public profile
-- and the owner's own portfolio total cannot disagree.
--
-- Scalar subqueries rather than joins deliberately: `user_public_profiles` has
-- exactly one table in its FROM and is therefore auto-updatable, and
-- account_router._do_account_delete issues `DELETE FROM user_public_profiles`.
-- Adding a JOIN or a target-list aggregate would make the view read-only and
-- turn account deletion into a 500 (the router only catches UndefinedTableError).

CREATE OR REPLACE VIEW public.user_public_profile_v1 AS
SELECT
    p.id AS user_id,
    COALESCE(p.display_name, p.username) AS display_handle,
    p.avatar_url,
    p.created_at,
    p.created_at AS updated_at,
    CASE WHEN COALESCE(
           (SELECT ps.show_item_count FROM user_privacy_settings ps WHERE ps.user_id = p.id),
           true)
         THEN (SELECT count(*) FROM items i
                WHERE i.user_id = p.id AND COALESCE(i.archived, false) = false)
         ELSE NULL
    END AS collection_count,
    CASE WHEN COALESCE(
           (SELECT ps.show_collection_value FROM user_privacy_settings ps WHERE ps.user_id = p.id),
           true)
         THEN (SELECT round(COALESCE(SUM(
                   COALESCE(
                     (SELECT pp.q50 FROM price_predictions pp
                       WHERE pp.item_ref = i.canonical_ref
                       ORDER BY pp.generated_at DESC LIMIT 1),
                     (SELECT qp.q50_eur FROM quick_predictions qp
                       WHERE qp.item_id = i.id
                       ORDER BY qp.created_at DESC LIMIT 1),
                     i.predicted_price_eur, i.estimated_value, 0)
                 ), 0)::numeric, 2)
                 FROM items i
                WHERE i.user_id = p.id AND COALESCE(i.archived, false) = false)
         ELSE NULL
    END AS collection_value_eur
FROM profiles p
WHERE COALESCE(NULLIF(p.display_name, ''::text), NULLIF(p.username, ''::text)) IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Discovery — hide users who opted out of being found (default TRUE)
-- ---------------------------------------------------------------------------
-- This view backs dataProvider.searchUsers, which is the app's only route to
-- another collector's profile (CategoryCollectorSearch → /users/[userId]).
-- You always match yourself, so opting out never hides you from your own search.

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
    p.created_at,
    CASE WHEN COALESCE(
           (SELECT ps.show_item_count FROM user_privacy_settings ps WHERE ps.user_id = p.id),
           true)
         THEN (SELECT count(*) FROM items i
                WHERE i.user_id = p.id AND COALESCE(i.archived, false) = false)
         ELSE NULL
    END AS collection_count,
    CASE WHEN COALESCE(
           (SELECT ps.show_collection_value FROM user_privacy_settings ps WHERE ps.user_id = p.id),
           true)
         THEN (SELECT round(COALESCE(SUM(
                   COALESCE(
                     (SELECT pp.q50 FROM price_predictions pp
                       WHERE pp.item_ref = i.canonical_ref
                       ORDER BY pp.generated_at DESC LIMIT 1),
                     (SELECT qp.q50_eur FROM quick_predictions qp
                       WHERE qp.item_id = i.id
                       ORDER BY qp.created_at DESC LIMIT 1),
                     i.predicted_price_eur, i.estimated_value, 0)
                 ), 0)::numeric, 2)
                 FROM items i
                WHERE i.user_id = p.id AND COALESCE(i.archived, false) = false)
         ELSE NULL
    END AS collection_value_eur
FROM profiles p
WHERE COALESCE(NULLIF(p.display_name, ''::text), NULLIF(p.username, ''::text)) IS NOT NULL
  AND (
    p.id = auth.uid()
    OR COALESCE(
         (SELECT ps.allow_discovery FROM user_privacy_settings ps WHERE ps.user_id = p.id),
         true)
  );
