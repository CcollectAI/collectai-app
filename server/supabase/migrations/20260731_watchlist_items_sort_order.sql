-- Give the watchlist-builder reorder buttons somewhere to persist to.
--
-- `app/watchlist-builder.tsx` has move-up / move-down controls that call
-- `updateWatchlistItem(id, { sortOrder })`. `watchlist_items` never had a
-- `sort_order` column, so `watchlistProvider.updateWatchlistItem` deliberately
-- dropped the field — leaving an EMPTY update payload. The chain then was:
--
--   .update({})            -> PostgREST matches 0 rows
--   .select(...).single()  -> PGRST116, HTTP 406 "The result contains 0 rows"
--   provider throws        -> handleMoveUp/Down catch fires
--   -> optimistic reorder rolled back + "Could not reorder. Please try again."
--
-- So reordering failed **every time**, visibly, for anyone who tried it.
-- Verified against prod 2026-07-31 by issuing the exact PATCH the provider
-- produces.
--
-- Nullable with no default: existing rows keep NULL and the UI falls back to
-- its previous priority-based ordering until the user actually reorders. A
-- NOT NULL default 0 would claim every row is deliberately ranked first.

BEGIN;

ALTER TABLE public.watchlist_items
  ADD COLUMN IF NOT EXISTS sort_order integer;

COMMENT ON COLUMN public.watchlist_items.sort_order IS
  'User-defined watchlist order from watchlist-builder move up/down. NULL = never reordered; readers fall back to priority ordering.';

-- Ordering is always per-user, and every read is RLS-scoped to auth.uid().
CREATE INDEX IF NOT EXISTS idx_watchlist_items_user_sort
  ON public.watchlist_items (user_id, sort_order NULLS LAST);

COMMIT;
