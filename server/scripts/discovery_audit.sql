-- Discovery audit: run ~30 queries designed to surface the OTHER classes
-- of silent bug like the six from the R50l audit.
--
-- Each query ends with a \echo line describing what a non-zero result means.
-- Run with: psql "$DB_DSN" -f discovery_audit.sql
--
-- Any query returning rows is a potential bug — investigate before dismissing.

\timing off
\pset pager off
\pset format aligned

-- ===========================================================================
-- A. REFERENTIAL INTEGRITY — rows pointing at things that don't exist
-- ===========================================================================

\echo '=== A1: price_predictions with item_ref not in category_items ==='
SELECT 'orphan_predictions' AS check_name, COUNT(*) AS violators
FROM public.price_predictions pp
WHERE pp.item_ref IS NOT NULL
  AND pp.item_ref LIKE '%:%'
  AND NOT EXISTS (
    SELECT 1 FROM public.category_items ci
    WHERE ci.category = split_part(pp.item_ref, ':', 1)
      AND ci.item_key = substring(pp.item_ref FROM position(':' IN pp.item_ref) + 1)
  );

\echo '=== A2: market_hits with item_ref not in category_items ==='
SELECT 'orphan_hits' AS check_name, COUNT(*) AS violators
FROM public.market_hits mh
WHERE mh.item_ref IS NOT NULL
  AND mh.item_ref LIKE '%:%'
  AND NOT EXISTS (
    SELECT 1 FROM public.category_items ci
    WHERE ci.category = split_part(mh.item_ref, ':', 1)
      AND ci.item_key = substring(mh.item_ref FROM position(':' IN mh.item_ref) + 1)
  );

\echo '=== A3: items with category not in known set ==='
SELECT 'unknown_item_category' AS check_name, i.category, COUNT(*) AS rows
FROM public.items i
WHERE i.category IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM public.category_items ci WHERE ci.category = i.category)
GROUP BY i.category
ORDER BY 3 DESC LIMIT 10;

-- ===========================================================================
-- B. FRESHNESS — stale data that should be live
-- ===========================================================================

\echo '=== B1: active Ridge categories with no predictions in the last 7 days ==='
SELECT 'stale_category_predictions' AS check_name, ci.category, COUNT(ci.*) AS items,
       MAX(pp.generated_at) AS last_prediction
FROM public.category_items ci
LEFT JOIN public.price_predictions pp ON pp.category = ci.category
  AND pp.generated_at > now() - interval '7 days'
GROUP BY ci.category
HAVING COUNT(pp.*) = 0
ORDER BY items DESC LIMIT 20;

\echo '=== B2: market_hits where seen_at is in the future (clock skew / bad parse) ==='
SELECT 'future_timestamps' AS check_name, COUNT(*) AS violators
FROM public.market_hits
WHERE seen_at > now() + interval '1 hour';

\echo '=== B3: price_predictions generated in the future ==='
SELECT 'future_predictions' AS check_name, COUNT(*) AS violators
FROM public.price_predictions
WHERE generated_at > now() + interval '1 hour';

\echo '=== B4: market_hits ended_at before seen_at (impossible) ==='
SELECT 'ended_before_seen' AS check_name, COUNT(*) AS violators
FROM public.market_hits
WHERE ended_at IS NOT NULL AND seen_at IS NOT NULL
  AND ended_at < seen_at - interval '1 day';

-- ===========================================================================
-- C. FLOW-THROUGH — pipelines that produce nothing despite running
-- ===========================================================================

\echo '=== C1: workers with 100% runs but 0 error status ratio below 5% ==='
-- This is the inverse: workers with error rate >10% that are marked "ok" in registry
SELECT 'high_error_workers' AS check_name, worker_name,
       COUNT(*) FILTER (WHERE status='error') AS errors,
       COUNT(*) AS runs,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status='error') / NULLIF(COUNT(*),0), 1) AS error_pct
FROM public.worker_runs
WHERE finished_at > now() - interval '24 hours'
GROUP BY worker_name
HAVING COUNT(*) FILTER (WHERE status='error') * 10 > COUNT(*)
ORDER BY error_pct DESC;

\echo '=== C2: market_hits arrived but no prediction for the same item_ref ==='
SELECT 'hits_without_predictions' AS check_name, category, COUNT(DISTINCT item_ref) AS unpredicted_items
FROM public.market_hits
WHERE item_ref IS NOT NULL AND item_ref LIKE '%:%'
  AND category IS NOT NULL
  AND seen_at > now() - interval '24 hours'
  AND NOT EXISTS (
    SELECT 1 FROM public.price_predictions pp
    WHERE pp.item_ref = market_hits.item_ref
      AND pp.generated_at > market_hits.seen_at
  )
GROUP BY category
ORDER BY 3 DESC LIMIT 15;

\echo '=== C3: calibration_snapshots still empty despite calibration_worker running ==='
SELECT 'empty_calibration_snapshots' AS check_name,
       (SELECT COUNT(*) FROM public.calibration_snapshots) AS total_snapshots,
       (SELECT COUNT(*) FROM public.worker_runs WHERE worker_name='calibration_worker' AND finished_at > now() - interval '7 days' AND status='ok') AS recent_ok_runs;

\echo '=== C4: spend events: zero rows despite paid workers being active ==='
SELECT 'spend_instrumentation_coverage' AS check_name,
       (SELECT COUNT(DISTINCT provider) FROM public.spend_events WHERE ts > now() - interval '7 days') AS providers_with_events,
       (SELECT COUNT(*) FROM public.worker_runs WHERE worker_name IN ('catalog_crawler_worker','marketplace_scrape_worker','event_scraper_worker') AND finished_at > now() - interval '7 days') AS relevant_worker_runs;

-- ===========================================================================
-- D. DUPLICATION — rows that should be unique
-- ===========================================================================

\echo '=== D1: duplicate user_settings per user ==='
SELECT 'duplicate_user_settings' AS check_name, user_id, COUNT(*) AS cnt
FROM public.user_settings GROUP BY user_id HAVING COUNT(*) > 1 LIMIT 10;

\echo '=== D2: duplicate watchlist_items per (user_id, title) ==='
SELECT 'duplicate_watchlist' AS check_name, user_id, title, COUNT(*) AS cnt
FROM public.watchlist_items GROUP BY user_id, title HAVING COUNT(*) > 1 LIMIT 10;

\echo '=== D3: duplicate category_items per (category, item_key) ==='
SELECT 'duplicate_category_items' AS check_name, category, item_key, COUNT(*) AS cnt
FROM public.category_items GROUP BY category, item_key HAVING COUNT(*) > 1 LIMIT 10;

\echo '=== D4: duplicate market_hits per (provider, listing_id) ==='
SELECT 'duplicate_market_hits' AS check_name, provider, listing_id, COUNT(*) AS cnt
FROM public.market_hits GROUP BY provider, listing_id HAVING COUNT(*) > 1 LIMIT 10;

-- ===========================================================================
-- E. NULL-RATE ANOMALIES — columns that should never be null but sometimes are
-- ===========================================================================

\echo '=== E1: NULL rates on critical market_hits columns ==='
SELECT 'market_hits_null_rates' AS check_name,
       ROUND(100.0 * COUNT(*) FILTER (WHERE title IS NULL) / COUNT(*), 2) AS pct_null_title,
       ROUND(100.0 * COUNT(*) FILTER (WHERE price IS NULL) / COUNT(*), 2) AS pct_null_price,
       ROUND(100.0 * COUNT(*) FILTER (WHERE category IS NULL) / COUNT(*), 2) AS pct_null_category,
       ROUND(100.0 * COUNT(*) FILTER (WHERE item_ref IS NULL) / COUNT(*), 2) AS pct_null_item_ref,
       ROUND(100.0 * COUNT(*) FILTER (WHERE provider IS NULL) / COUNT(*), 2) AS pct_null_provider,
       COUNT(*) AS total_rows
FROM public.market_hits WHERE seen_at > now() - interval '7 days';

\echo '=== E2: price_predictions.confidence is NULL (should always be computed) ==='
SELECT 'missing_confidence' AS check_name, COUNT(*) AS violators
FROM public.price_predictions
WHERE confidence IS NULL AND conf_score IS NULL
  AND generated_at > now() - interval '7 days';

-- ===========================================================================
-- F. ENUM DRIFT — string values outside the documented set
-- ===========================================================================

\echo '=== F1: user_settings.subscription_tier outside known set ==='
SELECT 'unknown_subscription_tier' AS check_name, subscription_tier, COUNT(*) AS cnt
FROM public.user_settings
WHERE subscription_tier IS NOT NULL
  AND subscription_tier NOT IN ('free', 'pro', 'premium')
GROUP BY subscription_tier;

\echo '=== F2: worker_runs.status outside known set ==='
SELECT 'unknown_worker_status' AS check_name, status, COUNT(*) AS cnt
FROM public.worker_runs
WHERE finished_at > now() - interval '7 days'
  AND status NOT IN ('ok', 'error')
GROUP BY status;

\echo '=== F3: mandate_deals.status outside known set ==='
SELECT 'mandate_deal_status' AS check_name, status, COUNT(*) AS cnt
FROM public.mandate_deals
GROUP BY status ORDER BY 2 DESC;

-- ===========================================================================
-- G. MODEL/DATA QUALITY — per-category health
-- ===========================================================================

\echo '=== G1: categories with >500 items but <10 market_hits (7d) — scraper starvation ==='
SELECT 'scraper_starved_categories' AS check_name, ci.category,
       COUNT(DISTINCT ci.item_key) AS catalog_size,
       COUNT(DISTINCT mh.id) FILTER (WHERE mh.seen_at > now() - interval '7 days') AS hits_7d
FROM public.category_items ci
LEFT JOIN public.market_hits mh ON mh.category = ci.category
GROUP BY ci.category
HAVING COUNT(DISTINCT ci.item_key) > 500
   AND COUNT(DISTINCT mh.id) FILTER (WHERE mh.seen_at > now() - interval '7 days') < 10
ORDER BY catalog_size DESC LIMIT 20;

\echo '=== G2: categories where max(q50) looks wrong (anomaly detection) ==='
SELECT 'quantile_outlier_categories' AS check_name, category,
       ROUND(MAX(q50)::numeric, 0) AS max_q50,
       ROUND(AVG(q50)::numeric, 0) AS avg_q50,
       ROUND((MAX(q50)/NULLIF(AVG(q50),0))::numeric, 1) AS max_over_avg,
       COUNT(*) AS n
FROM public.price_predictions
WHERE q50 IS NOT NULL AND generated_at > now() - interval '7 days'
GROUP BY category
HAVING MAX(q50)/NULLIF(AVG(q50),0) > 100
ORDER BY 4 DESC LIMIT 15;

-- ===========================================================================
-- H. CIRCUIT BREAKERS / ADAPTER HEALTH (if exposed in DB)
-- ===========================================================================

\echo '=== H1: adapters with >90% error rate (via worker_runs with adapter tag in metadata) ==='
SELECT 'high_error_adapters' AS check_name,
       metadata->>'adapter' AS adapter,
       COUNT(*) AS runs,
       COUNT(*) FILTER (WHERE status='error') AS errors
FROM public.worker_runs
WHERE finished_at > now() - interval '24 hours'
  AND metadata ? 'adapter'
GROUP BY 2
HAVING COUNT(*) FILTER (WHERE status='error') * 10 > COUNT(*) * 9
LIMIT 10;

-- ===========================================================================
-- I. SCHEMA SANITY — column sets that should match writer expectations
-- ===========================================================================

\echo '=== I1: market_hits: rows with price set but price_eur missing (fx bug) ==='
SELECT 'missing_fx_conversion' AS check_name, COUNT(*) AS violators
FROM public.market_hits
WHERE price IS NOT NULL AND price > 0 AND price_eur IS NULL
  AND seen_at > now() - interval '7 days';

\echo '=== I2: label_events: NULL user_id where schema expects UUID ==='
SELECT 'orphan_label_events' AS check_name, COUNT(*) AS violators
FROM public.label_events
WHERE user_id IS NULL
  AND created_at > now() - interval '30 days';

\echo '=== DONE — any check returning non-zero rows is a potential bug. ==='
