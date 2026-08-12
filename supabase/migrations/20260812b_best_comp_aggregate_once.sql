-- mv_item_best_comp_canon: scan market_hits ONCE, not once per item.
--
-- The durable half of the 2026-08-12 `hourly_refresh_best_comp` fix.
-- `20260812_speed_up_market_hits_canon.sql` took the refresh from 140.5 s to
-- 72.7 s by removing a correlated subquery, which got it back under the 120 s
-- statement_timeout. This removes the reason it was slow at all.
--
-- THE SHAPE. The definition was a LATERAL evaluated per item:
--
--   FROM v_items_canon i JOIN LATERAL (
--     SELECT h2.id FROM v_market_hits_canon h2
--     WHERE h2.canonical_category = i.canonical_category
--     ORDER BY h2.id DESC LIMIT 1) h ON true
--
-- `canonical_category` is COMPUTED, so no index can serve that predicate and
-- each of the 5 items drove a full scan of all 1.44M market_hits rows. The
-- aggregate below computes the same answer in ONE pass, grouped by category:
-- `max(mh.id)` is exactly `ORDER BY id DESC LIMIT 1` (id is bigint NOT NULL),
-- and the inner JOIN drops items with no matching hits exactly as the LATERAL
-- did (a LATERAL with LIMIT 1 and ON true yields no row when the subquery is
-- empty).
--
--   before  140.5 s
--   after     5.7 s      (~25x, measured on the live DB)
--
-- Output equivalence PROVEN before swapping, not assumed: both definitions
-- materialised in one session and EXCEPT-diffed in BOTH directions —
-- 0 rows each way, 5 rows each. `category_map.raw_category_lower` is the
-- PRIMARY KEY (72 rows / 72 distinct), so the LEFT JOIN cannot multiply rows.
--
-- WHY THE DANCE BELOW. A materialised view cannot be replaced in place, and
-- `DROP … CASCADE` would take `v_category_comp_coverage`,
-- `v_category_comp_coverage_canon` and `v_item_best_comp_full` with it — 96
-- grants between them, hand-restored, which is how a grant goes missing
-- silently. Instead: build the new one alongside, repoint the three dependents
-- with CREATE OR REPLACE VIEW (in place, so their own grants never move), drop
-- the old, then RENAME the new into its place. View dependencies are tracked by
-- OID, so after the rename the three dependents reference the original name
-- again with no further edits — and pg_cron job 16, which names
-- `public.mv_item_best_comp_canon` in its command text, keeps working untouched.
--
-- Every step is inside one transaction. DDL is transactional in Postgres, so a
-- failure anywhere leaves the old matview and all three dependents exactly as
-- they were.
--
-- Also drops a redundancy: the old matview carried TWO identical unique indexes
-- on (item_id) — `mv_item_best_comp_canon_item_uidx` and
-- `..._build_item_uidx` — both maintained on every refresh. One is recreated.
-- `REFRESH … CONCURRENTLY` requires exactly this unique index to exist.

BEGIN;

CREATE MATERIALIZED VIEW public.mv_item_best_comp_canon_v2 AS
SELECT i.id AS item_id,
       b.hit_id
FROM v_items_canon i
JOIN (
    SELECT COALESCE(m.canonical_category, lower(mh.category)) AS canonical_category,
           max(mh.id) AS hit_id
    FROM market_hits mh
    LEFT JOIN category_map m ON m.raw_category_lower = lower(mh.category)
    WHERE mh.category IS NOT NULL
      AND btrim(mh.category) <> ''::text
    GROUP BY 1
) b ON b.canonical_category = i.canonical_category
WITH DATA;

CREATE UNIQUE INDEX mv_item_best_comp_canon_v2_item_uidx
    ON public.mv_item_best_comp_canon_v2 (item_id);

-- Replicates the old ACL exactly: {postgres=arwdDxtm/postgres,
-- service_role=arwdDxtm/postgres, collector_bot=arwd/postgres}. postgres is the
-- owner and needs no explicit grant. On PG17 `arwdDxtm` includes MAINTAIN, which
-- is what lets a non-owner run REFRESH — GRANT ALL carries it.
--
-- The REVOKE is NOT redundant, and the dry run is what proved it. Supabase ships
-- DEFAULT PRIVILEGES on schema public that grant ALL to anon and authenticated
-- for newly created relations, so the fresh matview came out with
-- `anon=arwdDxtm` and `authenticated=arwdDxtm` — privileges the object being
-- replaced never had. A materialised view cannot carry RLS and `public` is the
-- PostgREST-exposed schema, so leaving that in place would hand anonymous
-- clients read access as a side effect of a performance fix. Recreating a
-- relation RESETS its ACL to the schema defaults; it does not inherit the old
-- object's grants.
REVOKE ALL ON public.mv_item_best_comp_canon_v2 FROM anon, authenticated;
GRANT ALL ON public.mv_item_best_comp_canon_v2 TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.mv_item_best_comp_canon_v2 TO collector_bot;

-- Repoint the three dependents. Bodies are verbatim from pg_get_viewdef; the
-- ONLY change in each is the matview name. CREATE OR REPLACE VIEW requires the
-- column list, order and types to be unchanged, which they are.

CREATE OR REPLACE VIEW public.v_category_comp_coverage AS
 SELECT i.category,
    count(i.id) AS total_items,
    count(mv.hit_id) AS items_with_hit,
    round(100.0 * count(mv.hit_id)::numeric / NULLIF(count(i.id), 0)::numeric, 2) AS coverage_pct
   FROM training_items i
     LEFT JOIN mv_item_best_comp_canon_v2 mv ON mv.item_id = i.id
  GROUP BY i.category
  ORDER BY (round(100.0 * count(mv.hit_id)::numeric / NULLIF(count(i.id), 0)::numeric, 2)) DESC NULLS LAST;

CREATE OR REPLACE VIEW public.v_category_comp_coverage_canon AS
 WITH items AS (
         SELECT i.id,
            i.canonical_category
           FROM v_items_canon i
        ), items_with_hits AS (
         SELECT mv.item_id,
            i.canonical_category
           FROM mv_item_best_comp_canon_v2 mv
             JOIN v_items_canon i ON i.id = mv.item_id
        )
 SELECT ct.wave,
    ct.code AS canonical_category,
    ct.display_name,
    count(DISTINCT items.id) AS total_items,
    count(DISTINCT items_with_hits.item_id) AS items_with_hit,
    round(100.0 * count(DISTINCT items_with_hits.item_id)::numeric / NULLIF(count(DISTINCT items.id), 0)::numeric, 2) AS coverage_pct
   FROM category_taxonomy ct
     LEFT JOIN items ON items.canonical_category = ct.code
     LEFT JOIN items_with_hits ON items_with_hits.canonical_category = ct.code
  WHERE COALESCE(ct.meta ->> 'status'::text, 'active'::text) <> 'deprecated'::text
  GROUP BY ct.wave, ct.code, ct.display_name;

CREATE OR REPLACE VIEW public.v_item_best_comp_full AS
 SELECT ti.id AS item_id,
    ti.category AS item_category,
    mv.hit_id,
    mh.id,
    mh.user_id,
    mh.title,
    mh.url,
    mh.price,
    mh.currency,
    mh.image_url,
    mh.marketplace,
    mh.seen_at,
    mh.item_ref,
    mh.category,
    mh.source,
    mh.observed_at,
    mh.condition_grade,
    mh.tx_id,
    mh.seller_rating,
    mh.url_hash
   FROM training_items ti
     JOIN mv_item_best_comp_canon_v2 mv ON mv.item_id = ti.id
     JOIN market_hits mh ON mh.id = mv.hit_id;

-- Nothing references the old one now.
DROP MATERIALIZED VIEW public.mv_item_best_comp_canon;

ALTER MATERIALIZED VIEW public.mv_item_best_comp_canon_v2
    RENAME TO mv_item_best_comp_canon;
ALTER INDEX public.mv_item_best_comp_canon_v2_item_uidx
    RENAME TO mv_item_best_comp_canon_item_uidx;

COMMIT;
