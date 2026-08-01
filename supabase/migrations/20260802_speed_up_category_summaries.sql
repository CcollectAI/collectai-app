-- v_category_summaries_v1: stop scanning the whole catalog per request.
--
-- The old definition joined ALL of category_items (221,391 rows) to the user's
-- items and aggregated down to 54 rows, on every call:
--
--   GroupAggregate (rows=54)
--     -> Incremental Sort (rows=221391)  temp read=394 written=396, peak disk 3.1MB
--       -> Nested Loop Left Join (rows=221391)
--          -> Index Scan on category_items   (rows=221391)
--          -> Materialize -> Index Scan on items   (rows=0)
--
-- 5029 ms cold / 140 ms warm. The cold path exceeded the client's 15s bound and
-- surfaced in the app as Postgres 57014 "canceling statement due to statement
-- timeout" on the Analytics screen (2026-08-02).
--
-- The insight: total_count is USER-INDEPENDENT. Only owned_count varies per
-- user. So aggregate the catalog once per category, and drive owned_count from
-- the user's items (a handful of rows) instead of from the catalog.
--
--   v1  5029 ms cold / 140 ms warm
--   v2   109 ms cold / 106 ms warm     (~47x cold, and no cold-cache cliff)
--
-- Output-equivalence PROVEN before swapping, not assumed: with a real
-- auth.uid() context for a user owning catalog-matched items (lorcana 2,
-- yugioh 1), an EXCEPT diff in both directions across all 54 categories
-- returned zero rows.
--
-- The join stays `category_items.item_key = items.canonical_key` — both are the
-- BARE key. CLAUDE.md "Identifier formats" warns this view depends on the bare
-- form; do NOT normalise canonical_key to namespaced. No new key pair, so
-- nothing to add to audit_key_overlap.py::PAIRS. No index added — governance
-- rule 1 in docs/DATA_SCALING_PLAN.md is "default = refuse to add", and the new
-- plan does not need one.

CREATE OR REPLACE VIEW public.v_category_summaries_v1 AS
WITH totals AS (
  SELECT ci.category, count(DISTINCT ci.id) AS total_count
  FROM category_items ci
  GROUP BY ci.category
),
owned AS (
  SELECT ci.category, count(DISTINCT ci.id) AS owned_count
  FROM items i
  JOIN category_items ci ON ci.item_key = i.canonical_key
  WHERE i.user_id = auth.uid()
  GROUP BY ci.category
)
SELECT t.category AS id,
       t.category AS name,
       t.total_count,
       COALESCE(o.owned_count, 0) AS owned_count,
       t.total_count - COALESCE(o.owned_count, 0) AS missing_count,
       CASE WHEN t.total_count = 0 THEN 0::numeric
            ELSE round(COALESCE(o.owned_count,0)::numeric / t.total_count::numeric * 100::numeric, 1)
       END AS completion_pct
FROM totals t
LEFT JOIN owned o ON o.category = t.category
ORDER BY t.category;

DROP VIEW IF EXISTS public.v_category_summaries_v2;
