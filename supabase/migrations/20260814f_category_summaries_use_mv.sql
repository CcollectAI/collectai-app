-- Point v_category_summaries_v1 at the materialised totals.
--
-- Output equivalence PROVEN before swapping, per the protocol in
-- docs/ANDROID_LAUNCH.md: `set_config('request.jwt.claims', …, FALSE)` — false,
-- not true, because a transaction-local setting would be gone by the next
-- statement and both snapshots would trivially match on auth.uid() = NULL — a
-- member who actually owns rows (6 of 55 categories non-zero), and EXCEPT in
-- BOTH directions. 55 rows before, 55 after, zero diff each way.
--
-- Measured on prod via PostgREST as `authenticated`, same member:
--   before the item_key index:  8.76s -> HTTP 500 (57014 statement timeout)
--   after the index:            7.58s cold, 0.59s warm
--   after this swap:            0.67s cold, 0.23s warm
CREATE OR REPLACE VIEW public.v_category_summaries_v1 AS
 WITH owned AS (
     SELECT ci.category, count(DISTINCT ci.id) AS owned_count
       FROM items i
       JOIN category_items ci ON ci.item_key = i.canonical_key
      WHERE i.user_id = auth.uid()
      GROUP BY ci.category
 )
 SELECT t.category AS id,
        t.category AS name,
        t.total_count,
        COALESCE(o.owned_count, 0::bigint) AS owned_count,
        t.total_count - COALESCE(o.owned_count, 0::bigint) AS missing_count,
        CASE WHEN t.total_count = 0 THEN 0::numeric
             ELSE round(COALESCE(o.owned_count, 0::bigint)::numeric
                        / t.total_count::numeric * 100::numeric, 1)
        END AS completion_pct
   FROM public.mv_category_totals t
   LEFT JOIN owned o ON o.category = t.category
  ORDER BY t.category;
