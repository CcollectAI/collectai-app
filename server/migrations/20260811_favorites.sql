-- Favorites — a plain "saved it" list, deliberately NOT a watchlist row.
--
-- WHY AN EIGHTH TABLE IN THIS SPACE
--
-- There are already seven: watchlist, watchlist_items, wish_items,
-- wishlist_items, wishlist_items_v1, wishlists, and the v_watchlist_items view.
-- Adding another needs a reason better than "it is easier".
--
-- The reason is that the alternative is a KNOWN BUG. `watchlist_items` is the
-- live one and it is snipe-capable: `_check_watchlist_snipes` filters
-- `WHERE target_price IS NOT NULL AND target_price > 0`, so a row saved with no
-- target is inert — it sits on the watchlist forever and can never fire. A
-- favourite heart wired to `addWatchlistItem` with no target was built on the
-- marketplace grid 2026-08-08 and removed the same day for exactly this, and
-- docs/alerts-and-insights.md records it as the FOURTH instance of that writer
-- bug. Storing "saved" in the alerting table is what produces it.
--
-- So: favouriting means saved, and promises nothing. Watching means a target
-- price and an alert. Two intents, two tables, neither lying about the other.
--
-- CREATE TABLE without IF NOT EXISTS is deliberate. IF NOT EXISTS is
-- name-idempotent, not SHAPE-idempotent: a differently-shaped pre-existing
-- `favorites` would make this a silent no-op that reports success forever
-- (learning_create_if_not_exists_silently_noops). Let it fail loudly instead.
BEGIN;

CREATE TABLE public.favorites (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL,

    -- Exactly one of these two is set — see the CHECK below.
    --   listing_id    → a live marketplace listing (disappears when it does)
    --   canonical_key → a catalogue item, which outlives any one listing
    listing_id    uuid REFERENCES public.marketplace_listings(id) ON DELETE CASCADE,

    -- BARE, never namespaced. `canonical_key` is bare everywhere;
    -- it is `*.item_ref` that carries the `source:` prefix. Getting this
    -- backwards is what left 44 joins matching nothing for four months
    -- (learning_canonical_key_vs_item_ref_namespace).
    canonical_key text,

    -- SLUG vocabulary ('mtg'), never a display name ('Magic: The Gathering').
    -- market_hits.category and watchlist_items.category are slugs, and a picker
    -- built from display names writing into a slug column is precisely how the
    -- watchlist writers were producing rows that matched nothing
    -- (learning_join_vocabulary_slug_vs_display_name).
    category      text,

    created_at    timestamptz NOT NULL DEFAULT now(),

    -- A row favourites a listing OR a catalogue item, never both and never
    -- neither. Without this, "which thing is this row about?" has no answer and
    -- every reader invents its own.
    CONSTRAINT favorites_one_target
        CHECK (num_nonnulls(listing_id, canonical_key) = 1)
);

-- The heart is a TOGGLE, so the write path is an upsert and these are what make
-- it idempotent. Partial, because a NULL in a plain UNIQUE would let a user
-- favourite the same listing many times over via the canonical_key arm.
CREATE UNIQUE INDEX favorites_user_listing_uniq
    ON public.favorites (user_id, listing_id)
    WHERE listing_id IS NOT NULL;

CREATE UNIQUE INDEX favorites_user_canonical_uniq
    ON public.favorites (user_id, canonical_key)
    WHERE canonical_key IS NOT NULL;

-- The Favorites screen's only query: newest first, for one user.
CREATE INDEX favorites_user_created ON public.favorites (user_id, created_at DESC);

ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;

-- Owner-only, and SELECT only — same shape as p2p_offers. Writes go through
-- the server router on the service role, so there is no client-side INSERT to
-- police here; if that ever changes, this policy set has to grow with it.
DROP POLICY IF EXISTS favorites_owner ON public.favorites;
CREATE POLICY favorites_owner ON public.favorites
    FOR SELECT USING (user_id = auth.uid());

COMMIT;
